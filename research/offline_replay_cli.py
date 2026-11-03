"""Offline, reproducible XAU/USD BID/ASK replay CLI.

Accepts user-supplied CSVs and provenance JSON; never downloads market data,
connects to a broker, or claims a data license. Signals are deterministic
illustrations, not a fitted trading policy.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from .dataset_evidence import dataset_manifest
from .costed_bid_ask_replay import replay_signals
from .pair_qualification import _rows
from .data_qualification import QualificationError


def evaluate(bid_path, ask_path, provenance, *, fee=0.0, slippage=0.0,
             holdout_fraction=0.25):
    if not (0 < holdout_fraction < 1) or not math.isfinite(holdout_fraction):
        raise QualificationError("holdout fraction must be between zero and one")
    if not all(math.isfinite(x) and x >= 0 for x in (fee, slippage)):
        raise QualificationError("costs must be finite and nonnegative")
    manifest = dataset_manifest(bid_path, ask_path, provenance=provenance)
    bid = list(_rows(bid_path))
    count = len(bid)
    boundary = int(count * (1 - holdout_fraction))
    if boundary < 3 or count - boundary < 3:
        raise QualificationError("insufficient candles for disjoint holdout replay")
    # A decision at candle i uses only known BID closes i and i-1.
    signal = [0] * count
    for i in range(1, count):
        delta = bid[i][4] - bid[i-1][4]
        signal[i] = (1 if delta > 0 else -1 if delta < 0 else 0)
    # A trade decided at i fills at i+1 and exits at i+2.
    # Disallow any training trade touching holdout candles.
    training = [s if i + 2 < boundary else 0 for i, s in enumerate(signal)]
    # Holdout decisions start at boundary and can never use earlier outcomes
    # for policy optimization (the rule is fixed before evaluation).
    testing = [s if i >= boundary else 0 for i, s in enumerate(signal)]
    train_result = replay_signals(bid_path, ask_path, training,
                                  provenance=provenance, fee_per_round_trip=fee,
                                  slippage_per_side=slippage)
    test_result = replay_signals(bid_path, ask_path, testing,
                                 provenance=provenance, fee_per_round_trip=fee,
                                 slippage_per_side=slippage)
    def metrics(result):
        return {k: result[k] for k in
                ("trades", "net_per_unit", "max_drawdown_per_unit", "win_rate")}
    return {"manifest": manifest, "rule": "fixed one-candle bid-close momentum",
            "holdout_start_index": boundary, "training": metrics(train_result),
            "holdout": metrics(test_result), "holdout_evaluated_once": True,
            "license_verified": False, "execution_authorized": False,
            "warning": "Illustrative research replay only. No fitted model, statistical alpha or license certification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bid", required=True)
    parser.add_argument("--ask", required=True)
    parser.add_argument("--provenance", required=True, help="Path to provenance JSON")
    parser.add_argument("--fee", type=float, default=0.0)
    parser.add_argument("--slippage", type=float, default=0.0)
    parser.add_argument("--holdout-fraction", type=float, default=0.25)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    provenance = json.loads(Path(args.provenance).read_text(encoding="utf-8"))
    result = evaluate(args.bid, args.ask, provenance, fee=args.fee,
                      slippage=args.slippage, holdout_fraction=args.holdout_fraction)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                 encoding="utf-8")


if __name__ == "__main__":
    main()
