"""Behavioural exploration regressions against authoritative toy replay."""
import copy
from math import nan

import pytest

from agentic_trading.behavior_probe import mutation_behavior_probe
from agentic_trading.evolution_tower import GENES, TowerError, evaluate, initial_state, make_tape


def test_observational_trace_preserves_exact_fitness_and_fills():
    tape = make_tape(55, 192)
    genes = list(initial_state(seed=31)["population"][0]["genes"])
    before = list(genes)
    untraced = evaluate(genes, tape)
    traced = evaluate(genes, tape, capture_behavior=True)
    assert {k: v for k, v in traced.items() if k != "behavior"} == untraced
    assert genes == before
    b = traced["behavior"]
    assert b["decision_bars"] == sum(b["action_counts"].values())
    assert b["decision_bars"] <= len(tape) - 25
    assert b["entries"] == traced["trades"]
    assert b["closed_positions"] == traced["closed_trades"]
    assert len(b["decision_sha256"]) == 64
    assert b["broker_orders"] == 0


def test_flat_hold_and_close_are_not_reported_as_filled_trades():
    tape = make_tape(22, 192)
    for action_offset, label in ((88, "HOLD"), (91, "CLOSE")):
        genes = [0.] * GENES
        genes[action_offset] = 5.
        result = evaluate(genes, tape, capture_behavior=True)
        trace = result["behavior"]
        assert result["trades"] == 0
        assert result["fitness"] == 0
        assert trace["flat_abstentions"] == trace["decision_bars"]
        assert trace["action_counts"][label] == trace["decision_bars"]
    genes = [0.] * GENES
    genes[89] = 5.
    bought = evaluate(genes, tape, capture_behavior=True)
    assert bought["trades"] == bought["behavior"]["entries"]
    assert bought["behavior"]["reversals"] == 0
    assert bought["behavior"]["action_counts"]["BUY"] > 0


def test_probe_is_repeatable_and_measures_real_action_changes():
    tape = make_tape(55, 192)
    baseline = [0.] * GENES  # HOLD tie, genuinely flat
    probe = mutation_behavior_probe(baseline, tape, seed=123, mirrored_pairs=8, sigma=0.3)
    assert probe == mutation_behavior_probe(baseline, tape, seed=123, mirrored_pairs=8, sigma=0.3)
    assert probe["variants_evaluated"] == 16
    assert probe["changed_decision_variants"] + probe["unchanged_decision_variants"] == 16
    assert probe["changed_decision_variants"] > 0
    assert probe["unique_decision_signatures_including_baseline"] >= 2
    assert probe["baseline_behavior"]["entries"] == 0
    assert not probe["fitness_used_to_select_models"]
    assert not probe["qualified"] and not probe["applied_to_student"]
    assert not probe["paper_trading_enabled"] and not probe["live_trading_enabled"]


def test_probe_never_changes_saved_student_or_limits():
    state = initial_state(seed=2026)
    original = copy.deepcopy(state)
    mutation_behavior_probe(state["population"][0]["genes"], make_tape(7, 192), mirrored_pairs=2)
    assert state == original
    assert state["paper_trading_enabled"] is False
    assert state["live_trading_enabled"] is False


@pytest.mark.parametrize("overrides", [
    {"mirrored_pairs": 0}, {"mirrored_pairs": 33},
    {"mirrored_pairs": True}, {"sigma": 0},
    {"sigma": 0.9}, {"sigma": nan}, {"seed": True},
])
def test_probe_rejects_invalid_controls(overrides):
    with pytest.raises(TowerError):
        mutation_behavior_probe([0.] * GENES, make_tape(1, 192), **overrides)


def test_probe_rejects_nonfinite_model_or_invalid_tape():
    with pytest.raises(TowerError):
        mutation_behavior_probe([nan] * GENES, make_tape(1, 192))
    with pytest.raises(TowerError):
        mutation_behavior_probe([0.] * GENES, [1.] * 3)
