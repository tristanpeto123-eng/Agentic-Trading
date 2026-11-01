"""Offline-only tests for bounded output-bias exploration."""
import copy

import pytest

from agentic_trading.bounded_bias_exploration import explore_action_biases
from agentic_trading.evolution_tower import GENES, TowerError, initial_state, make_tape


def _toy():
    return make_tape(39012, 384), make_tape(50013, 192)


def test_saturated_student_probes_actual_behaviour_without_mutating_model():
    state = initial_state(seed=20261101)
    original = copy.deepcopy(state)
    train, diagnostic = _toy()
    genes = state["population"][0]["genes"]  # original BUY explorer
    result = explore_action_biases(genes, train, diagnostic)
    assert state == original
    assert result["training_evaluations"] == 26
    assert result["diagnostic_evaluations"] == 2
    assert len(result["variants"]) == 24
    assert result["selected_train_fitness"] >= result["baseline_train_fitness"]
    assert result["mutants_with_changed_action_sequence"] > 0
    assert result["model_applied_to_student"] is False
    assert result["qualified"] is False
    assert result["paper_trading_enabled"] is False
    assert result["live_trading_enabled"] is False
    assert result["diagnostic_did_not_select_weights"] is True
    assert len(result["report_sha256"]) == 64


def test_flat_student_does_not_fake_profit_or_force_entry():
    flat = [0.0] * GENES
    flat[88] = 3.0
    train, diagnostic = _toy()
    report = explore_action_biases(flat, train, diagnostic)
    assert report["baseline_train_fitness"] == 0
    assert report["selected_train_fitness"] >= 0
    if report["selected_train_behavior"]["entries"] == 0:
        assert report["no_trade_is_not_profitability"]
    assert not report["qualified"]


def test_deterministic_report_and_identical_research_budget():
    train, diagnostic = _toy()
    genes = tuple(initial_state(seed=20261103)["population"][2]["genes"])
    one = explore_action_biases(genes, train, diagnostic)
    two = explore_action_biases(genes, train, diagnostic)
    assert one == two
    assert one["training_evaluations"] == 26
    assert one["diagnostic_evaluations"] == 2


@pytest.mark.parametrize("invalid_genes", [
    [0.0] * (GENES - 1),
    [float("nan")] * GENES,
    [True] * GENES,
    [4.0] * GENES,
])
def test_invalid_model_rejected(invalid_genes):
    train, diagnostic = _toy()
    with pytest.raises(TowerError):
        explore_action_biases(invalid_genes, train, diagnostic)


def test_identical_or_invalid_tapes_rejected():
    train, _ = _toy()
    model = [0.0] * GENES
    with pytest.raises(TowerError, match="must differ"):
        explore_action_biases(model, train, train)
    with pytest.raises(TowerError):
        explore_action_biases(model, [100.0] * 30, make_tape(2, 192))
    with pytest.raises(TowerError):
        explore_action_biases(model, train, [float("inf")] * 192)
