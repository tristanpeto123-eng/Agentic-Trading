"""Immutable walk-forward research fold manifests with a sealed final test.

Computes strictly chronological index windows and hashes. This creates no
real-data certification, no execution tape, and no trading authorization.
Training, feature generation and inference MUST independently respect the
emitted bounds. The final test is never returned as a data slice here.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from math import isfinite
from typing import Sequence
import json

from agentic_trading.contracts.common import require_utc


class WalkForwardError(ValueError):
    pass


@dataclass(frozen=True)
class WalkForwardPlan:
    manifest: dict
    manifest_sha256: str
    research_only: bool = True
    independent_evidence_verified: bool = False
    qualified: bool = False


def _hash(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plan_walk_forward(
    candles: Sequence[object],
    *,
    min_train: int,
    validation_bars: int,
    step_bars: int,
    embargo_bars: int,
    sealed_test_bars: int,
    min_folds: int = 3,
) -> WalkForwardPlan:
    """Expanding training history, rolling development validation, final sealed test.

    Only bounded index/clock ranges are emitted. The last N rows stay untouched
    by every development fold and are not exposed as returned candle records.
    One embargo on each side of the final test and train->validation boundary.
    No future close information should be used by a signal generator.
    """
    n = len(candles)
    if any(not isinstance(x,int) or isinstance(x,bool) for x in
           (min_train, validation_bars, step_bars, embargo_bars, sealed_test_bars, min_folds)):
        raise WalkForwardError("fold sizes must be integers")
    if (min_train < 100 or validation_bars < 30 or step_bars < 1
            or embargo_bars < 1 or sealed_test_bars < 50 or min_folds < 2):
        raise WalkForwardError("unsafe or undersized fold settings")
    if step_bars > validation_bars:
        raise WalkForwardError("step cannot exceed validation duration: uncovered development interval")
    dates = []
    canonical = []
    previous = None
    for idx, candle in enumerate(candles):
        try:
            stamp = candle.open_time
            require_utc(stamp)
            if previous is not None and stamp <= previous:
                raise WalkForwardError("timestamps must be strictly increasing")
            prices = [float(getattr(candle, field)) for field in ("open","high","low","close")]
            op, hi, lo, cl = prices
            if (not all(isfinite(p) and p > 0 for p in prices)
                    or lo > min(op,cl) or hi < max(op,cl) or hi < lo):
                raise WalkForwardError("invalid candle prices")
            vol = getattr(candle, "volume", None)
            if vol is not None and (not isfinite(float(vol)) or float(vol) < 0):
                raise WalkForwardError("invalid volume")
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise WalkForwardError(f"invalid candle at index {idx}: {exc}") from exc
        dates.append(stamp)
        canonical.append([stamp.isoformat(), *(str(getattr(candle,k)) for k in
                          ("open","high","low","close")), str(vol)])
        previous = stamp
    test_start = n - sealed_test_bars
    development_end = test_start - embargo_bars
    validation_start = min_train + embargo_bars
    folds = []
    while validation_start + validation_bars <= development_end:
        train_end = validation_start - embargo_bars
        validation_end = validation_start + validation_bars
        folds.append({
            "fold": len(folds)+1,
            "train": {"start": 0, "end_exclusive": train_end,
                      "first_utc": dates[0].isoformat(), "last_utc": dates[train_end-1].isoformat()},
            "validation": {"start": validation_start, "end_exclusive": validation_end,
                           "first_utc": dates[validation_start].isoformat(),
                           "last_utc": dates[validation_end-1].isoformat()},
        })
        validation_start += step_bars
        if len(folds) > 100:
            raise WalkForwardError("at most 100 folds per research plan")
    if len(folds) < min_folds:
        raise WalkForwardError("insufficient history for independent development folds")
    source = sha256(json.dumps(canonical,separators=(",",":")).encode()).hexdigest()
    manifest = {
        "schema": "walk_forward_plan.v1",
        "source_sha256": source,
        "total_rows": n,
        "embargo_bars": embargo_bars,
        "sealed_test": {
            "start": test_start, "end_exclusive": n,
            "first_utc": dates[test_start].isoformat(),
            "last_utc": dates[-1].isoformat(),
            "accessible_to_development": False,
        },
        "development_end_exclusive": development_end,
        "folds": folds,
        "restrictions": {
            "fit_only_on_train": True,
            "selection_only_on_validation": True,
            "final_test_access_for_model_selection": False,
            "provenance_independently_verified": False,
            "paper_and_live_eligible": False,
        },
    }
    return WalkForwardPlan(manifest, _hash(manifest))


def verify_walk_forward_manifest(candles: Sequence[object], plan: WalkForwardPlan) -> bool:
    """Reconstruct and compare SHA of source + chronological interval boundaries."""
    data = plan.manifest
    folds = data.get("folds", ())
    if not folds or data.get("schema") != "walk_forward_plan.v1":
        raise WalkForwardError("missing or invalid manifest")
    first = folds[0]
    expected = plan_walk_forward(
        candles, min_train=first["train"]["end_exclusive"],
        validation_bars=first["validation"]["end_exclusive"]-first["validation"]["start"],
        step_bars=(folds[1]["validation"]["start"]-first["validation"]["start"])
                    if len(folds)>1 else 0,
        embargo_bars=data["embargo_bars"],
        sealed_test_bars=len(candles)-data["sealed_test"]["start"],
        min_folds=len(folds),
    )
    if expected.manifest_sha256 != plan.manifest_sha256 or expected.manifest != data:
        raise WalkForwardError("fold/source manifest does not match original data and plan")
    return True
