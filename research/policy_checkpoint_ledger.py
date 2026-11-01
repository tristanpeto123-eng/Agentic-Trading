"""Versioned research checkpoint ledger with five-batch gate integration.

This is an auditable policy checkpoint manager, NOT a model trainer.
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from .walkforward_policy_gates import PolicyCandidate, policy_gate, GateError


class CheckpointLedger:
    def __init__(self, path: str | Path, *, frozen_skill_fingerprint: str):
        if not frozen_skill_fingerprint.strip():
            raise GateError("missing frozen skill fingerprint")
        self.path = Path(path)
        self.fingerprint = frozen_skill_fingerprint

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as stream:
            records = json.load(stream)
        if not isinstance(records, list):
            raise GateError("invalid checkpoint ledger")
        return records

    def propose(self, candidate: PolicyCandidate, *, baseline_net: float,
                max_allowed_drawdown: float, min_improvement: float = 0) -> dict:
        """Persist a qualified proposal; never auto-promote or execute."""
        verdict = policy_gate(candidate, baseline_net=baseline_net,
                              max_allowed_drawdown=max_allowed_drawdown,
                              expected_fingerprint=self.fingerprint,
                              min_improvement=min_improvement)
        if not verdict["qualified"]:
            return verdict
        records = self.read()
        if any(record.get("version") == candidate.version for record in records):
            raise GateError("checkpoint version already exists")
        proposal = {"version": candidate.version,
                    "frozen_skill_fingerprint": candidate.frozen_skill_fingerprint,
                    "batches_seen": candidate.batches_seen,
                    "validation_net": candidate.validation_net,
                    "validation_max_drawdown": candidate.validation_max_drawdown,
                    "state": "proposed", "held_out_test_verified": False,
                    "ceo_approved": False, "execution_authorized": False}
        records.append(proposal)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".checkpoint-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(records, stream, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"qualified": True, "state": "proposed",
                "execution_authorized": False, "version": candidate.version}
