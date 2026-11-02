"""Adapter between offline training snapshots and immutable checkpoint proposals.

No broker access. A proposed checkpoint is NOT approved for execution.
"""
from __future__ import annotations
import math
from .walkforward_policy_gates import PolicyCandidate, GateError
from .policy_checkpoint_ledger import CheckpointLedger


def propose_training_snapshot(ledger: CheckpointLedger, snapshot, *,
                              validation_max_drawdown: float,
                              baseline_net: float,
                              max_allowed_drawdown: float,
                              min_improvement: float = 0.0) -> dict:
    if not math.isfinite(validation_max_drawdown) or validation_max_drawdown < 0:
        raise GateError("invalid validation drawdown")
    candidate = PolicyCandidate(
        version=f"policy-{snapshot.version}-batch-{snapshot.batches_seen}",
        frozen_skill_fingerprint=snapshot.skill_fingerprint,
        batches_seen=snapshot.batches_seen,
        validation_net=snapshot.validation_net,
        validation_max_drawdown=validation_max_drawdown)
    return ledger.propose(candidate, baseline_net=baseline_net,
                          max_allowed_drawdown=max_allowed_drawdown,
                          min_improvement=min_improvement)
