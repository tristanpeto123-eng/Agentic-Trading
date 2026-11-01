"""Minimal five-batch policy selector trainer, for offline research only.

Each batch supplies net-after-cost rewards per frozen skill. Updates choose
between existing skills; they do not modify skill implementations.
"""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass


class TrainingError(ValueError):
    pass


@dataclass(frozen=True)
class PolicySnapshot:
    version: int
    batches_seen: int
    skill_fingerprint: str
    preferred_skill: str
    validation_net: float


class FiveBatchPolicyTrainer:
    def __init__(self, frozen_skills: tuple[str, ...]):
        if not frozen_skills or len(set(frozen_skills)) != len(frozen_skills) or any(not s for s in frozen_skills):
            raise TrainingError("skills must be unique and nonempty")
        self.skills = frozen_skills
        self.fingerprint = hashlib.sha256(json.dumps(frozen_skills).encode()).hexdigest()
        self.batches: list[dict[str, float]] = []
        self.snapshots: list[PolicySnapshot] = []

    def ingest_batch(self, net_rewards: dict[str, float], *,
                     validation_rewards: dict[str, float] | None = None) -> PolicySnapshot | None:
        if set(net_rewards) != set(self.skills):
            raise TrainingError("missing or unexpected skill rewards")
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in net_rewards.values()):
            raise TrainingError("nonfinite batch reward")
        # Validation is only supplied at checkpoint time; it is never used for skill ranking.
        if (len(self.batches) + 1) % 5 == 0:
            if validation_rewards is None or set(validation_rewards) != set(self.skills):
                raise TrainingError("checkpoint requires complete held-out validation rewards")
            if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in validation_rewards.values()):
                raise TrainingError("nonfinite validation reward")
        elif validation_rewards is not None:
            raise TrainingError("validation only allowed at five-batch checkpoint")
        self.batches.append(dict(net_rewards))
        if len(self.batches) % 5:
            return None
        # Rank by cumulative realized net training rewards across the latest 5 batches.
        scores = {skill: sum(batch[skill] for batch in self.batches[-5:]) for skill in self.skills}
        winner = max(self.skills, key=lambda skill: (scores[skill], -self.skills.index(skill)))
        snapshot = PolicySnapshot(len(self.snapshots) + 1, len(self.batches),
                                  self.fingerprint, winner, validation_rewards[winner])
        self.snapshots.append(snapshot)
        return snapshot
