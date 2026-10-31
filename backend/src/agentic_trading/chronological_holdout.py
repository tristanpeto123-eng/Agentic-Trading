"""Chronological, embargoed splits for offline market research only.

Splitting a file is not proof that an agent never accessed the held-out data.
The training runner must enforce access separation independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite
from typing import Iterable

from agentic_trading.contracts.common import require_utc


@dataclass(frozen=True)
class EmbargoedSplit:
    train: tuple[object, ...]
    validation: tuple[object, ...]
    test: tuple[object, ...]
    embargo_bars: int
    source_sha256: str
    manifest_sha256: str
    research_only: bool = True
    qualified: bool = False

    @property
    def counts(self) -> dict[str, int]:
        return {
            "train": len(self.train), "validation": len(self.validation),
            "test": len(self.test), "embargoed": self.embargo_bars * 4,
        }


def split_chronological(
    candles: Iterable[object],
    *,
    embargo_bars: int = 96,
    minimum_per_fold: int = 100,
) -> EmbargoedSplit:
    """60% train / 20% validation / 20% test with barred boundary buffers.

    Discards 'embargo_bars' on *both* sides of the two split boundaries,
    so adjacent label windows cannot be assumed independent. The caller must
    choose embargo >= the longest label/features lookahead used by a strategy.
    """
    if embargo_bars < 1:
        raise ValueError("embargo_bars must be positive")
    if minimum_per_fold < 1:
        raise ValueError("minimum_per_fold must be positive")
    rows = tuple(candles)
    n = len(rows)
    train_end = n * 60 // 100
    test_start = n * 80 // 100
    train = rows[:train_end - embargo_bars]
    validation = rows[train_end + embargo_bars:test_start - embargo_bars]
    test = rows[test_start + embargo_bars:]
    if min(map(len, (train, validation, test))) < minimum_per_fold:
        raise ValueError("Not enough rows to retain 3 folds after embargo")
    previous: datetime | None = None
    canonical = []
    for index, candle in enumerate(rows):
        try:
            stamp = getattr(candle, "open_time")
            require_utc(stamp)
            if previous is not None and stamp <= previous:
                raise ValueError("Input candles must be strictly chronological")
            raw = tuple(getattr(candle, field) for field in ("open", "high", "low", "close"))
            op, hi, lo, cl = (float(value) for value in raw)
            if not all(isfinite(value) and value > 0 for value in (op, hi, lo, cl)):
                raise ValueError("Prices must be finite and strictly positive")
            if lo > hi or lo > min(op, cl) or hi < max(op, cl):
                raise ValueError("Invalid OHLC bounds")
            volume = getattr(candle, "volume", None)
            if volume is not None:
                numeric_volume = float(volume)
                if not isfinite(numeric_volume) or numeric_volume < 0:
                    raise ValueError("Volume must be finite and non-negative")
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid candle at index {index}: {exc}") from exc
        previous = stamp
        canonical.append([
            stamp.isoformat(),
            *(str(value) for value in raw),
            str(volume),
        ])
    source_sha = sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()
    manifest = {
        "schema": "embargoed_holdout.v1",
        "source_sha256": source_sha,
        "rows": n, "embargo_bars": embargo_bars,
        "train_end_exclusive_index": train_end - embargo_bars,
        "validation_start_index": train_end + embargo_bars,
        "validation_end_exclusive_index": test_start - embargo_bars,
        "test_start_index": test_start + embargo_bars,
    }
    manifest_sha = sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return EmbargoedSplit(
        train=train, validation=validation, test=test,
        embargo_bars=embargo_bars,
        source_sha256=source_sha,
        manifest_sha256=manifest_sha,
    )
