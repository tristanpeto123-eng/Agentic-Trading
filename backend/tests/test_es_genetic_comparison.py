"""Baseline comparison uses strictly isolated bounded training calls."""
import math

import pytest

from agentic_trading.es_research import ESConfig, ESResearchError
from agentic_trading.es_genetic_comparison import compare_es_and_genetic_mutation


def bowl(v):
    return -(v[0] - 0.65) ** 2 - (v[1] + 0.45) ** 2


def test_equal_budgets_and_diagnostic_only_after_policy_freeze():
    counter = {"train": 0, "diagnostic": 0}
    def train(weights):
        assert counter["diagnostic"] == 0
        counter["train"] += 1
        return bowl(weights)
    def diagnostic(weights):
        counter["diagnostic"] += 1
        return -(weights[0] - 0.1) ** 2
    config = ESConfig(seed=24, generations=4, mirrored_pairs=6)
    report = compare_es_and_genetic_mutation((0., 0.), train, diagnostic, config=config)
    expected = 1 + 4 * 13
    assert report["train_fitness_evaluations_each"] == expected
    assert counter == {"train": 2 * expected, "diagnostic": 3}
    assert report["diagnostic_fitness_evaluations_total"] == 3
    for name in ("es", "genetic_mutation_control"):
        assert report[name]["train_fitness"] >= report["training_baseline_fitness"]
        assert math.isfinite(report[name]["diagnostic_fitness"])
    assert report["comparison_is_full_evolution_tower"] is False
    assert report["independent_validation"] is False
    assert report["qualified"] is False
    assert report["paper_trading_enabled"] is False
    assert report["live_trading_enabled"] is False


def test_exact_determinism():
    config = ESConfig(seed=12, generations=3, mirrored_pairs=5)
    one = compare_es_and_genetic_mutation((0.1, -0.2), bowl, bowl, config=config)
    two = compare_es_and_genetic_mutation((0.1, -0.2), bowl, bowl, config=config)
    assert one == two
    assert len(one["report_sha256"]) == 64


def test_constant_fitness_abstention_not_misreported_as_skill():
    report = compare_es_and_genetic_mutation((0., 0.), lambda _: 0., lambda _: 0.,
                                              config=ESConfig(generations=2, mirrored_pairs=2))
    assert report["es"]["train_fitness"] == 0.
    assert report["genetic_mutation_control"]["train_fitness"] == 0.
    assert report["es"]["diagnostic_fitness"] == 0.
    assert not report["qualified"]


def test_invalid_diagnostic_and_budgets_fail_closed():
    with pytest.raises(ESResearchError, match="finite"):
        compare_es_and_genetic_mutation((0.,), lambda x: x[0], lambda _: float('nan'),
                                        config=ESConfig(generations=1, mirrored_pairs=2))
    with pytest.raises(ESResearchError, match="budget"):
        compare_es_and_genetic_mutation((0.,), lambda x: x[0], lambda x: x[0],
                                        config=ESConfig(generations=30, mirrored_pairs=64))
