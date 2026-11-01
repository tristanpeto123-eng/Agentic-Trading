#!/usr/bin/env python3
"""Finite, deterministic ATL ES experiment on toy synthetic prices ONLY.

Usage: python scripts/run_es_research.py --generations 5 --pairs 8
This is not a daemon and makes no network or broker calls.
"""
import argparse
import json

from agentic_trading.es_research import ESConfig, run_es_research
from agentic_trading.evolution_tower import evaluate, initial_state, make_tape


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--pairs", type=int, default=8)
    args = parser.parse_args()

    # Existing frozen toy random walk, not a real CFD market sample.
    train_tape = make_tape(seed=39012, count=384)
    diagnostic_tape = make_tape(seed=50013, count=192)
    original = tuple(initial_state(seed=20261101)["population"][0]["genes"])

    def fitness(weights):
        return evaluate(list(weights), train_tape)["fitness"]

    experiment = run_es_research(
        original, fitness,
        config=ESConfig(generations=args.generations, mirrored_pairs=args.pairs),
    )
    # Diagnostic tape is used exactly once AFTER the training loop. It does
    # not influence training acceptance and is NOT an independent qualification.
    final = tuple(experiment.pop("final_weights"))
    result = {
        "schema": "atl_es_toy_demo.v1", "source_kind": "SYNTHETIC_RANDOM_WALK_ONLY",
        "mode": "offline_research", "optimizer": experiment,
        "training_metrics": evaluate(list(final), train_tape),
        "diagnostic_metrics": evaluate(list(final), diagnostic_tape),
        "diagnostic_selection_allowed": False,
        "independent_exam": False, "trading_authority": False,
    }
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
