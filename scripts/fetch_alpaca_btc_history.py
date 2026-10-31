#!/usr/bin/env python3
"""Save bounded BTC/USD Alpaca history OUTSIDE public GitHub, on explicit opt-in.

An opt-in to acquisition is not independent provider licence certification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from agentic_trading.providers.alpaca_crypto_history import (
    CryptoDataError, fetch_private_btc_history,
)

REPOSITORY = Path(__file__).resolve().parents[1]


def _parse_utc(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DDTHH:MM:SSZ") from exc
    if result.utcoffset() != timezone.utc.utcoffset(None):
        raise argparse.ArgumentTypeError("Start and end must be UTC")
    return result


def _write_once(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise CryptoDataError("Immutable output differs; refusing overwrite")
        return
    with path.open("xb") as out:
        out.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-utc", required=True, type=_parse_utc)
    parser.add_argument("--until-utc", required=True, type=_parse_utc)
    parser.add_argument("--kind", choices=("bars", "quotes"), default="bars")
    parser.add_argument("--timeframe", choices=("1Hour", "1Day"), default="1Hour")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--fetch", action="store_true",
                        help="Opt in to bounded provider GET requests")
    parser.add_argument("--private-research-only", action="store_true",
                        help="Acknowledge personal, non-commercial, non-redistributed research only")
    args = parser.parse_args()
    destination = args.out_dir.resolve()
    if destination == REPOSITORY or destination.is_relative_to(REPOSITORY):
        parser.error("Private destination MUST be outside the public Git repository")
    try:
        snapshot = fetch_private_btc_history(
            start=args.from_utc, end=args.until_utc, kind=args.kind,
            timeframe="quote" if args.kind == "quotes" else args.timeframe,
            allow_network=args.fetch,
            private_research_acknowledged=args.private_research_only,
        )
        destination.mkdir(parents=True, exist_ok=True)
        stem = "btc_" + args.kind + "_" + snapshot.report["canonical_sha256"][:12]
        _write_once(destination / (stem + ".jsonl"), snapshot.canonical_jsonl)
        _write_once(destination / (stem + ".manifest.json"),
                    (json.dumps(snapshot.report, indent=2, sort_keys=True) + "\n").encode())
        print("Private quarantine complete; rows:", snapshot.report["records"])
        print("Manifest SHA-256:", snapshot.report["canonical_sha256"])
        print("Rights and paper/live qualification remain UNVERIFIED and DISABLED.")
        return 0
    except (CryptoDataError, OSError) as exc:
        parser.exit(2, f"Alpaca private capture refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
