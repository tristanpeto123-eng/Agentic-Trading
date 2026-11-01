#!/usr/bin/env python3
"""Finite CPU-only exploration of 92-weight toy students. Never a broker."""
import json

from agentic_trading.bounded_bias_exploration import explore_action_biases
from agentic_trading.evolution_tower import initial_state, make_tape


def main():
    train, diagnostic = make_tape(39012, 384), make_tape(50013, 192)
    runs = []
    for i, starter in enumerate(("BUY_EXPLORER", "SELL_EXPLORER", "UNBIASED_RANDOM")):
        seed = 20261101 + i
        genes = initial_state(seed=seed)["population"][i]["genes"]
        report = explore_action_biases(genes, train, diagnostic)
        runs.append({
            "starter": starter,
            "seed": seed,
            "baseline_train_fitness": report["baseline_train_fitness"],
            "selected_train_fitness": report["selected_train_fitness"],
            "baseline_diagnostic_fitness": report["baseline_diagnostic_fitness"],
            "selected_diagnostic_fitness": report["selected_diagnostic_fitness"],
            "baseline_train_entries": report["baseline_train_behavior"]["entries"],
            "selected_train_entries": report["selected_train_behavior"]["entries"],
            "mutants_with_changed_action_sequence": report["mutants_with_changed_action_sequence"],
            "best_train_choice": report["best_train_choice"],
            "selected_nontrading": report["no_trade_is_not_profitability"],
            "report_sha256": report["report_sha256"],
        })
    output = {
        "schema": "atl_bias_exploration_demo.v1",
        "data_kind": "SYNTHETIC_RANDOM_WALK_ONLY",
        "runs": runs, "research_only": True,
        "model_activation": False,
        "no_claim_of_profitability": True,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
