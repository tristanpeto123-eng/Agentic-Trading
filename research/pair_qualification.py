"""Pair-side checks and auditable provenance for research-only CSV data."""
from __future__ import annotations
import csv
import datetime as dt
import math
from pathlib import Path
from .data_qualification import QualificationError, qualify_csv


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            yield (dt.datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                   *(float(row[k]) for k in ("open", "high", "low", "close")))


def qualify_pair(bid_path: str | Path, ask_path: str | Path, *,
                 provenance: dict, expected_seconds: int = 60) -> dict:
    """Reject mismatched timestamps, crossed spreads and unrecorded source metadata.

    Positive structural results are NOT proof of data licensing or market validity.
    """
    required = ("provider", "instrument", "source_url", "retrieved_utc",
                "license_reference", "permitted_use")
    if any(not isinstance(provenance.get(key), str) or not provenance[key].strip()
           for key in required):
        raise QualificationError("incomplete source provenance")
    if provenance["instrument"].upper() not in ("XAUUSD", "XAU/USD"):
        raise QualificationError("unexpected instrument")
    try:
        retrieved = dt.datetime.fromisoformat(provenance["retrieved_utc"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise QualificationError("invalid provenance retrieval time") from exc
    if retrieved.utcoffset() != dt.timedelta(0):
        raise QualificationError("retrieval time must be UTC")
    bid = qualify_csv(bid_path, side="BID", expected_seconds=expected_seconds)
    ask = qualify_csv(ask_path, side="ASK", expected_seconds=expected_seconds)
    if bid["candles"] != ask["candles"]:
        raise QualificationError("different candle counts")
    max_spread = 0.0
    for index, (b, a) in enumerate(zip(_rows(bid_path), _rows(ask_path)), start=2):
        if b[0] != a[0]:
            raise QualificationError(f"line {index}: timestamp mismatch")
        for field in range(1, 5):
            spread = a[field] - b[field]
            if not math.isfinite(spread) or spread < 0:
                raise QualificationError(f"line {index}: crossed {('open','high','low','close')[field-1]} quote")
            max_spread = max(max_spread, spread)
    return {"candles": bid["candles"], "max_observed_spread": max_spread,
            "provenance": provenance, "qualified_structure_only": True,
            "license_verified": False, "execution_authorized": False}
