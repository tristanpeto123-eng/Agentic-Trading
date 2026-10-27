"""Fail-closed qualification evidence for historical research datasets.

This module never authorizes paper or live execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Iterable


@dataclass(frozen=True)
class QualificationReport:
    dataset_sha256: str
    rows: int
    issues: tuple[str, ...]
    train_rows: int
    validation_rows: int
    test_rows: int
    research_eligible: bool
    paper_eligible: bool = False
    live_eligible: bool = False

    def as_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True)


def assess_candles(
    candles: Iterable[object],
    *,
    provenance_verified: bool = False,
    rights_verified: bool = False,
    minimum_rows: int = 1000,
) -> QualificationReport:
    """Validate ordered UTC OHLC candles and reserve chronological holdout.

    Never equate basic dataset quality with profitable trading or Registrar approval.
    """
    rows = list(candles)
    issues: list[str] = []
    previous = None
    canonical = []
    for index, candle in enumerate(rows):
        try:
            stamp = candle.open_time
            values = tuple(float(getattr(candle, field)) for field in ("open", "high", "low", "close"))
            if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("timestamp must be timezone-aware")
            if stamp.utcoffset().total_seconds() != 0:
                raise ValueError("timestamp must be UTC")
            from math import isfinite
            if not all(isfinite(v) and v > 0 for v in values):
                raise ValueError("prices must be finite and positive")
            op, hi, lo, cl = values
            if lo > min(op, cl) or hi < max(op, cl) or lo > hi:
                raise ValueError("invalid OHLC bounds")
            if previous is not None and stamp <= previous:
                raise ValueError("timestamps must strictly increase")
            previous = stamp
            canonical.append([stamp.isoformat(), *values])
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            issues.append(f"row {index}: {exc}")
    if len(rows) < minimum_rows:
        issues.append(f"insufficient rows: {len(rows)} < {minimum_rows}")
    if not provenance_verified:
        issues.append("source provenance unverified")
    if not rights_verified:
        issues.append("data rights unverified")
    n = len(rows)
    train = n * 60 // 100
    validation = n * 20 // 100
    test = n - train - validation
    digest = sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()
    return QualificationReport(
        dataset_sha256=digest, rows=n, issues=tuple(issues),
        train_rows=train, validation_rows=validation, test_rows=test,
        research_eligible=not issues,
    )
