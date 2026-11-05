"""Research-only Academy checkpoint -> Tower population lineage.

Only existing Academy checkpoint records are eligible parents. This module
creates immutable population *descriptors*; runtime model cloning/loading
must be implemented by the caller. No broker access or auto-promotion.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AcademyCheckpoint:
    student_id: str
    checkpoint_id: str
    model_sha256: str
    skill_fingerprint: str
    qualified: bool = False


@dataclass(frozen=True)
class TowerAgent:
    agent_id: str
    parent_student_id: str
    parent_checkpoint_id: str
    inherited_model_sha256: str
    inherited_skill_fingerprint: str
    variant_seed: int
    generation: int = 0
    execution_authorized: bool = False


def create_tower_population(checkpoints: list[AcademyCheckpoint], *,
                            size: int = 16, seed: int = 0) -> list[TowerAgent]:
    """Allocate 16 traceable descendants from approved research checkpoints.

    Qualified means the checkpoint passed Academy research validation, NOT
    approval to trade. Rejected/invalid checkpoints cannot seed the Tower.
    """
    if size != 16:
        raise ValueError("Tower population must contain exactly 16 agents")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    eligible = [c for c in checkpoints if c.qualified]
    if not eligible:
        raise ValueError("no qualified Academy checkpoints available")
    if len({c.checkpoint_id for c in eligible}) != len(eligible):
        raise ValueError("duplicate checkpoint ids")
    for c in eligible:
        if not c.student_id or not c.checkpoint_id or not c.skill_fingerprint:
            raise ValueError("incomplete Academy checkpoint")
        if len(c.model_sha256) != 64 or any(x not in "0123456789abcdef" for x in c.model_sha256):
            raise ValueError("invalid model SHA256")
    result = []
    for i in range(size):
        parent = eligible[i % len(eligible)]
        payload = json.dumps([seed, i, parent.student_id, parent.checkpoint_id],
                             separators=(",", ":"))
        variant_seed = int(hashlib.sha256(payload.encode()).hexdigest()[:12], 16)
        result.append(TowerAgent(
            agent_id=f"tower-g0-{i+1:02d}",
            parent_student_id=parent.student_id,
            parent_checkpoint_id=parent.checkpoint_id,
            inherited_model_sha256=parent.model_sha256,
            inherited_skill_fingerprint=parent.skill_fingerprint,
            variant_seed=variant_seed))
    return result


def population_manifest(agents: list[TowerAgent]) -> dict:
    if len(agents) != 16 or len({a.agent_id for a in agents}) != 16:
        raise ValueError("invalid Tower population")
    return {"schema_version": 1, "population": [asdict(a) for a in agents],
            "models_cloned": False, "execution_authorized": False}
