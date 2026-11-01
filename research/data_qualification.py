"""Strict, broker-independent BID/ASK candle qualification.

This module does not establish licensing rights or permit execution.
"""
from __future__ import annotations
import csv
import datetime as dt
import math
from pathlib import Path


class QualificationError(ValueError):
    pass


def qualify_csv(path: str | Path, *, side: str, expected_seconds: int = 60) -> dict:
    """Validate a single OHLC stream with UTC ISO-8601 timestamps.

    Requires columns timestamp,open,high,low,close. Rejects gaps rather than
    interpolating market prices. Licensing must be reviewed separately.
    """
    if side not in ("BID", "ASK"):
        raise QualificationError("side must be BID or ASK")
    if expected_seconds <= 0:
        raise QualificationError("expected_seconds must be positive")
    previous = None
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"timestamp", "open", "high", "low", "close"}
        if not required.issubset(reader.fieldnames or []):
            raise QualificationError("missing required columns")
        for line, row in enumerate(reader, start=2):
            try:
                stamp = dt.datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                if stamp.tzinfo is None or stamp.utcoffset() != dt.timedelta(0):
                    raise ValueError("timestamp must be UTC")
                values = [float(row[k]) for k in ("open", "high", "low", "close")]
                o, h, l, c = values
                if not all(math.isfinite(x) and x > 0 for x in values):
                    raise ValueError("prices must be finite and positive")
                if l > min(o, c) or h < max(o, c) or l > h:
                    raise ValueError("invalid OHLC range")
                if previous is not None:
                    delta = (stamp - previous).total_seconds()
                    if delta != expected_seconds:
                        raise ValueError(f"non-contiguous candle interval: {delta}s")
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                raise QualificationError(f"line {line}: {exc}") from exc
            previous = stamp
            count += 1
    if count < 2:
        raise QualificationError("at least two candles required")
    return {"side": side, "candles": count, "last_utc": previous.isoformat(), "qualified_structure_only": True, "license_verified": False, "execution_authorized": False}
