#!/usr/bin/env python3
"""Download Dukascopy public M1 BID/ASK files on demand, export M15 CSVs.

Requires installed local backend: `pip install -e './backend[dev]'`.
Runs offline unless --download is explicitly passed. Does not grant data-use rights.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import json

from agentic_trading.providers.dukascopy import ProviderError, collect, build_export


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", required=True, type=date.fromisoformat)
    parser.add_argument("--to-date", required=True, type=date.fromisoformat,
                        help="UTC exclusive end date")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--download", action="store_true", help="Opt in to bounded provider HTTP downloads")
    parser.add_argument("--pause-seconds", type=float, default=1.5)
    options = parser.parse_args()
    if options.cache_dir.resolve() == options.out_dir.resolve():
        parser.error("Source cache and output directory must differ")
    try:
        candles, sources = collect(options.from_date, options.to_date, cache_dir=options.cache_dir,
                                   download=options.download, pause_seconds=options.pause_seconds)
        now = datetime.now(timezone.utc)
        report, files = build_export(candles, sources, acquired_at=now)
        options.out_dir.mkdir(parents=True, exist_ok=True)
        for side, content in files.items():
            dest = options.out_dir / f"XAUUSD_{options.from_date}_{options.to_date}_M15_{side}.csv"
            dest.write_text(content, encoding="utf-8")
            print(f"Created {dest} ({report['sides'][side]['m15_count']} candles)")
        dest = options.out_dir / "dukascopy_provenance.json"
        dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Provenance report: {dest}; missing source files: {len(report['missing_sources'])}")
        print("QUARANTINED: licensing and independent source verification are not complete.")
        return 0
    except (ProviderError, OSError) as exc:
        parser.exit(2, f"Data source incomplete or invalid: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
