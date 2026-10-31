#!/usr/bin/env python3
"""Local-only structural audit of owner-supplied XAUUSD M1 BID/ASK OHLC.

The timestamps are candle opens. Synchronized BID/ASK candle *closes* are
indicative spread proxies, not executable simultaneous tick quotes. No source
licence or authenticity can be certified by a CSV inspection.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from statistics import median
import json

EXPECTED_SECONDS = 60
MAX_BYTES = 100_000_000
MAX_GAP_EXAMPLES = 20


class QuoteAuditError(ValueError):
    pass


def _read_quotes(path: Path) -> tuple[dict, dict[datetime, tuple[Decimal, Decimal, Decimal, Decimal]]]:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise QuoteAuditError("Missing or oversized market quote file")
    raw = path.read_bytes()
    try:
        body = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise QuoteAuditError("Quote CSV must be UTF-8") from exc
    lines = body.splitlines()
    if not lines:
        raise QuoteAuditError("Quote CSV is empty")
    reader = csv.DictReader(lines)
    if reader.fieldnames not in (
        ["Etc/UTC", "Open", "High", "Low", "Close", "Volume"],
        ["time", "open", "high", "low", "close", "volume"],
    ):
        raise QuoteAuditError("Unexpected quote schema")
    time_field = reader.fieldnames[0]
    price_fields = reader.fieldnames[1:5]
    points = {}
    prev = None
    gaps = []
    for line_no, row in enumerate(reader, 2):
        try:
            stamp = datetime.fromisoformat(row[time_field].replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
                raise ValueError("timestamp is not UTC")
            if stamp.second or stamp.microsecond:
                raise ValueError("not aligned to M1")
            if prev is not None and stamp <= prev:
                raise ValueError("duplicate/out-of-order timestamps")
            if prev is not None and (stamp - prev).total_seconds() > EXPECTED_SECONDS:
                if len(gaps) < MAX_GAP_EXAMPLES:
                    gaps.append({"previous_open_utc": prev.isoformat(),
                                 "next_open_utc": stamp.isoformat(),
                                 "missing_m1_intervals": int((stamp - prev).total_seconds() // 60) - 1})
            raw_prices = tuple(Decimal(row[k]) for k in price_fields)
            if not all(price.is_finite() and price > 0 for price in raw_prices):
                raise ValueError("nonfinite or nonpositive quote")
            op, hi, lo, cl = raw_prices
            if hi < max(op, cl) or lo > min(op, cl) or lo > hi:
                raise ValueError("invalid OHLC bounds")
            volume = Decimal(row[reader.fieldnames[5]])
            if not volume.is_finite() or volume < 0:
                raise ValueError("invalid volume")
        except (TypeError, KeyError, InvalidOperation, ValueError, AttributeError) as exc:
            raise QuoteAuditError(f"Invalid row {line_no}: {exc}") from exc
        points[stamp] = raw_prices
        prev = stamp
    if not points:
        raise QuoteAuditError("No complete quote candles")
    stamps = tuple(points)
    return (
        {"file_sha256": sha256(raw).hexdigest(), "rows": len(points),
         "first_utc": stamps[0].isoformat(), "last_utc": stamps[-1].isoformat(),
         "gap_examples": gaps, "gaps_require_session_calendar_review": bool(gaps)},
        points,
    )


def audit_bid_ask(bid_path: Path, ask_path: Path) -> dict:
    bid_info, bid = _read_quotes(bid_path)
    ask_info, ask = _read_quotes(ask_path)
    common = sorted(set(bid) & set(ask))
    if not common:
        raise QuoteAuditError("No synchronized M1 timestamps in BID/ASK files")
    close_spreads = []
    for stamp in common:
        diff = ask[stamp][3] - bid[stamp][3]
        if diff <= 0:
            raise QuoteAuditError(f"Non-positive M1 close spread at {stamp.isoformat()}")
        close_spreads.append(diff)
    report = {
        "schema": "xauusd_m1_bid_ask_structural_audit.v1",
        "instrument": "XAUUSD",
        "granularity": "M1",
        "quote_basis": "BID and ASK OHLC candles; not tick-level executable quotes",
        "bid": bid_info, "ask": ask_info,
        "aligned_m1_rows": len(common),
        "bid_only_rows": len(bid) - len(common),
        "ask_only_rows": len(ask) - len(common),
        "alignment_fraction": str((Decimal(len(common)) / Decimal(max(len(bid), len(ask)))).quantize(Decimal("0.000001"))),
        "overlap_first_utc": common[0].isoformat(),
        "overlap_last_utc": common[-1].isoformat(),
        "close_spread_usd_per_oz": {
            "min": str(min(close_spreads)),
            "median": str(median(close_spreads)),
            "max": str(max(close_spreads)),
        },
        "source_authenticity_independently_verified": False,
        "data_usage_rights_independently_verified": False,
        "historical_coverage_requirement_met": False,
        "model_exam_performed": False,
        "paper_trading_eligible": False,
        "live_trading_eligible": False,
        "note": "Structural candle comparison only. Licence, provider calendar and real executable tick data need separate verification.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bid_csv", type=Path)
    parser.add_argument("ask_csv", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    try:
        report = audit_bid_ask(args.bid_csv, args.ask_csv)
    except (OSError, QuoteAuditError) as exc:
        parser.exit(2, f"BID/ASK audit rejected: {exc}\n")
    result = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
