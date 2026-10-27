#!/usr/bin/env python3
"""Offline XAUUSD M15 dataset audit. Does not import to a broker or qualify trading.

Usage: python scripts/audit_xauusd_archive.py path/to/owner.csv --output report.json
Requires installed agentic_trading backend. Original prices are not printed or uploaded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from agentic_trading.data_engine import DataQualityError
from agentic_trading.qualification_bridge import inspect_historical_csv


def audit_file(path: Path, *, acquired_at: datetime | None = None) -> dict:
    """Read bytes as UTF-8 and produce private structural evidence only."""
    try:
        csv_content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise DataQualityError("Unable to read a UTF-8 historical CSV") from exc
    report = inspect_historical_csv(
        csv_content,
        acquired_at or datetime.now(timezone.utc),
    )
    report["audit_kind"] = "owner_supplied_offline_structural_check"
    report["source_provenance_claimed"] = False
    report["qualification"]["research_eligible"] = False
    report["qualification"]["paper_eligible"] = False
    report["qualification"]["live_eligible"] = False
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Local XAUUSD M15 CSV file")
    parser.add_argument("--output", type=Path, help="Private JSON report path; stdout when omitted")
    args = parser.parse_args()
    try:
        report = audit_file(args.csv)
    except (DataQualityError, ValueError) as exc:
        parser.exit(2, f"Archive rejected: {exc}\n")
    result = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
