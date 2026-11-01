#!/usr/bin/env python3
"""Finite research diagnostic: are student action patterns actually changing?"""
import argparse
import json
from hashlib import sha256

from agentic_trading.behavior_probe import mutation_behavior_probe
from agentic_trading.evolution_tower import initial_state, make_tape


def digest(data):
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--pairs", type=int, default=8, choices=range(1, 33))
    parser.add_argument("--sigma", type=float, default=0.06)
    args = parser.parse_args()

    train = make_tape(39012, 384)
    experiments = []
    for index in range(args.seeds):
        seed = 20261101 + index
        starter = index % 3
        saved = initial_state(seed=seed)
        student = saved["population"][starter]
        report = mutation_behavior_probe(student["genes"], train, seed=seed,
                                         mirrored_pairs=args.pairs, sigma=args.sigma)
        experiments.append({
            "seed": seed,
            "starter": ("BUY_EXPLORER", "SELL_EXPLORER", "UNBIASED_RANDOM")[starter],
            "diagnostic": report,
        })
    output = {
        "schema": "atl_policy_behavior_diagnostic.v1",
        "market_data": "SYNTHETIC_RANDOM_WALK_ONLY",
        "train_tape_sha256": digest(train),
        "experiments": experiments,
        "separate_probe_replays_not_training_budget": True,
        "independent_validation": False,
        "research_only": True,
        "automatic_model_activation": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }
    output["report_sha256"] = digest(output)
    print(json.dumps(output, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
