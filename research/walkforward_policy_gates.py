"""Research-only walk-forward partitions and five-batch policy update gates.

No model training is claimed here: this controls when an external trainer may
propose a checkpoint and whether held-out results permit promotion.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence


class GateError(ValueError):
    pass


@dataclass(frozen=True)
class Window:
    train: tuple[int, int]
    validate: tuple[int, int]
    test: tuple[int, int]


def walkforward_windows(n: int, *, train: int, validate: int, test: int,
                        step: int | None = None) -> list[Window]:
    """Generate chronological, disjoint windows with no test/train overlap per fold."""
    if any(type(v) is not int or v <= 0 for v in (n, train, validate, test)):
        raise GateError("window lengths must be positive integers")
    stride = test if step is None else step
    if type(stride) is not int or stride <= 0:
        raise GateError("step must be positive")
    windows = []
    for start in range(0, n - train - validate - test + 1, stride):
        a = start + train
        b = a + validate
        c = b + test
        windows.append(Window((start, a), (a, b), (b, c)))
    if not windows:
        raise GateError("insufficient candles for one fold")
    return windows


@dataclass(frozen=True)
class PolicyCandidate:
    version: str
    frozen_skill_fingerprint: str
    batches_seen: int
    validation_net: float
    validation_max_drawdown: float


def policy_gate(candidate: PolicyCandidate, *, baseline_net: float,
                max_allowed_drawdown: float, expected_fingerprint: str,
                min_improvement: float = 0.0) -> dict:
    """Return qualification, never execute orders or train a model."""
    if candidate.batches_seen <= 0 or candidate.batches_seen % 5:
        return {"qualified": False, "reason": "five-batch cadence not met"}
    if candidate.frozen_skill_fingerprint != expected_fingerprint:
        return {"qualified": False, "reason": "frozen skills changed"}
    if not candidate.version.strip() or not expected_fingerprint.strip():
        return {"qualified": False, "reason": "missing checkpoint identity"}
    import math
    metrics = (candidate.validation_net, candidate.validation_max_drawdown,
               baseline_net, max_allowed_drawdown, min_improvement)
    if not all(math.isfinite(x) for x in metrics) or max_allowed_drawdown < 0 or min_improvement < 0:
        raise GateError("invalid gate metrics")
    if candidate.validation_max_drawdown < 0 or candidate.validation_max_drawdown > max_allowed_drawdown:
        return {"qualified": False, "reason": "drawdown gate failed"}
    if candidate.validation_net < baseline_net + min_improvement:
        return {"qualified": False, "reason": "validation improvement gate failed"}
    return {"qualified": True, "reason": "validation gate passed; held-out test and CEO approval still required",
            "execution_authorized": False, "live_authorized": False}
