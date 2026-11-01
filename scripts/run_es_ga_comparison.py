#!/usr/bin/env python3
"""Compare offline ES vs Tower-style Gaussian-mutation CONTROL on toy tapes.

No broker, data-provider connections, model activation, or persistent job queue.
This command always terminates after its finite test budget.
"""
import argparse
import json
from hashlib import sha256

from agentic_trading.es_research import ESConfig
from agentic_trading.es_genetic_comparison import compare_es_and_genetic_mutation
from agentic_trading.evolution_tower import evaluate, initial_state, make_tape


def _sha(data):
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--seeds", type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    train = make_tape(seed=39012, count=384)
    diagnostic = make_tape(seed=50013, count=192)
    if _sha(train) == _sha(diagnostic):
        raise RuntimeError("training and diagnostic tape hashes collided")
    reports = []
    for i in range(args.seeds):
        seed = 20261101 + i
        original = tuple(initial_state(seed=seed)["population"][0]["genes"])

        def train_fitness(weights):
            return evaluate(list(weights), train)["fitness"]

        def diagnostic_fitness(weights):
            return evaluate(list(weights), diagnostic)["fitness"]

        report = compare_es_and_genetic_mutation(
            original, train_fitness, diagnostic_fitness,
            config=ESConfig(seed=seed, generations=args.generations,
                            mirrored_pairs=args.pairs),
        )
        reports.append({"seed": seed, "report": report})
    result = {
        "schema": "atl_es_ga_toy_comparison.v1",
        "market_data": "SYNTHETIC_RANDOM_WALK_ONLY",
        "train_tape_sha256": _sha(train),
        "diagnostic_tape_sha256": _sha(diagnostic),
        "comparative_method": "mirrored_ES_vs_tower_style_mutation_control_not_full_tower",
        "runs": reports,
        "interpretation": "Research comparison only; no market edge, qualification or deployment",
        "research_only": True,
        "sealed_holdout_used": False,
        "automated_student_checkpointing": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }
    result["report_sha256"] = _sha(result)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
