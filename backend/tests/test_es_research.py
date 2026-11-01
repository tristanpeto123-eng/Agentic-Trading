"""Pure offline ES research; no broker/data API access or qualifications."""
from math import nan

import pytest

from agentic_trading.es_research import ESConfig, ESResearchError, run_es_research


def bowl(x):
    return -sum((v - t) ** 2 for v, t in zip(x, (0.65, -0.45)))


def test_research_improves_frozen_objective_reproducibly():
    cfg = ESConfig(seed=24, generations=10, mirrored_pairs=16, learning_rate=.07)
    run = run_es_research((0., 0.), bowl, config=cfg)
    assert run == run_es_research((0., 0.), bowl, config=cfg)
    assert run["final_train_fitness"] > run["initial_train_fitness"]
    assert run["fitness_evaluations"] == 1 + 10 * (2 * 16 + 1)
    assert run["research_only"] and not run["qualified"]
    assert not run["paper_trading_enabled"] and not run["live_trading_enabled"]
    assert not run["independent_validation"] and not run["applied_to_student"]
    assert len(run["report_sha256"]) == 64


def test_zero_signal_never_invents_learning():
    run = run_es_research((0.1, -0.1), lambda _: 0., config=ESConfig(generations=2, mirrored_pairs=4))
    assert run["final_weights"] == [0.1, -0.1]
    assert all(not entry["accepted"] for entry in run["generations"])


def test_fitness_is_finite_and_research_is_bounded():
    for fitness in (lambda _: nan, lambda _: None, lambda _: True):
        with pytest.raises(ESResearchError, match="fitness"):
            run_es_research((0.0,), fitness)
    for invalid in (ESConfig(generations=31), ESConfig(mirrored_pairs=65),
                    ESConfig(sigma=0), ESConfig(learning_rate=1),
                    ESConfig(generations=30, mirrored_pairs=64)):
        with pytest.raises(ESResearchError):
            run_es_research((0.0,), lambda x: x[0], config=invalid)
    with pytest.raises(ESResearchError, match="initial policy"):
        run_es_research((nan,), lambda _: 1.0)


def test_client_inputs_remain_immutable_and_ledger_is_explicit():
    initial = [0., 0.]
    run_es_research(initial, bowl, config=ESConfig(generations=2, mirrored_pairs=4))
    assert initial == [0., 0.]
