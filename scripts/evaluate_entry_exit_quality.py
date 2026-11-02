#!/usr/bin/env python3
"""Offline entry/exit candidate comparison on authorised owner-local BID/ASK CSV.

Requires side-separated UTC CSVs with timestamp/open/high/low/close columns.
Source metadata is self-declared and NEVER counts as licence attestation.
Never submit vendor candles or account credentials to public GitHub.
"""
import argparse
import json
from pathlib import Path

from research.entry_exit_quality import EntryExitPlan, evaluate_entry_exit_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bid_csv", type=Path)
    parser.add_argument("ask_csv", type=Path)
    parser.add_argument("--provenance-json", type=Path, required=True,
                        help="Locally stored provider/source/rights metadata; assertions remain unverified")
    parser.add_argument("--output", type=Path, help="Write private report; never raw candles")
    parser.add_argument("--lookback", type=int, default=5)
    parser.add_argument("--holding", type=int, default=3)
    parser.add_argument("--latency", type=int, default=1)
    args = parser.parse_args()
    with args.provenance_json.open("r", encoding="utf-8") as handle:
        provenance = json.load(handle)
    result = evaluate_entry_exit_candidates(
        args.bid_csv, args.ask_csv, provenance=provenance,
        plan=EntryExitPlan(lookback=args.lookback, holding=args.holding, latency=args.latency),
    )
    output = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print("Saved private research report. No permissions granted:", args.output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
