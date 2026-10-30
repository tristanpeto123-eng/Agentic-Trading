"""Scenario accounting is not price verification, executable fills or model training."""
from dataclasses import replace
from decimal import Decimal

import pytest

from agentic_trading.candle_study import CandleStudyError
from agentic_trading.m15_trade_scenario import AssumedCosts, study_costed_outcomes
from test_candle_study import sample, SOURCE


def evaluate(bars=None, **kwargs):
    return study_costed_outcomes(
        sample() if bars is None else bars,
        dataset_id="test-quarantined-archive", source_sha256=SOURCE,
        embargo_bars=24, batch_size=48, **kwargs,
    )


def test_costed_good_bad_archive_is_hypothetical_and_reproducible():
    result = evaluate()
    assert result == evaluate()
    assert result["schema_version"] == "m15_hypothetical_cost_scenario.v1"
    assert result["mode"] == "scenario_assumed_m15_next_open_to_close"
    assert result["training"]["closed"] > 30
    assert result["training"]["good"] + result["training"]["bad"] + result["training"]["flat"] == result["training"]["closed"]
    assert result["holdout_evaluated"] is False
    assert result["sealed_holdout_bars"] > 0
    assert not result["source_verified"]
    assert not result["fill_assumptions_independently_validated"]
    assert not result["trade_execution_performed"]
    assert not result["neural_training_performed"]
    assert not result["durable_trade_memory_written"]
    assert not result["model_promotion_allowed"]
    assert not result["paper_trading_enabled"]
    assert not result["live_trading_enabled"]
    assert result["round_trip_cost_usd_per_oz"] == "1.00"
    assert result["hypothetical_outcome_preview"]
    for t in result["hypothetical_outcome_preview"]:
        assert t["signal_at"] == t["entry_at"]
        assert t["outcome"] in ("good", "bad", "flat")


def test_selector_changes_at_most_on_five_batch_boundaries():
    result = evaluate()
    batches = result["batches"]
    assert len(batches) >= 10
    for i, item in enumerate(batches):
        assert item["batch"] == i + 1
        assert item["selector_version"] == i // 5 + 1
        assert item["selector_updated_after"] == ((i+1) % 5 == 0)
        if i > 0 and i % 5:
            assert item["selected_rule"] == batches[i-1]["selected_rule"]
    assert result["selector_version"] == 1 + len(batches) // 5
    assert result["development_validation"]["selector_frozen"] is True


def test_higher_illustrative_execution_friction_reduces_net_for_fixed_rule():
    # Restrict to a single rule so costs cannot alter model selection.
    base = evaluate(allowed_tactics=("trend",), assumptions=AssumedCosts(
        full_spread_usd_per_oz=Decimal("0.25"),
        slippage_usd_per_oz_per_side=Decimal("0"),
        commission_usd_per_oz_per_side=Decimal("0"),
    ))
    high = evaluate(allowed_tactics=("trend",), assumptions=AssumedCosts(
        full_spread_usd_per_oz=Decimal("1.50"),
        slippage_usd_per_oz_per_side=Decimal("0.30"),
        commission_usd_per_oz_per_side=Decimal("0.10"),
    ))
    assert base["training"]["closed"] == high["training"]["closed"]
    assert Decimal(high["training"]["net_usd"]) < Decimal(base["training"]["net_usd"])
    assert Decimal(high["training"]["cost_usd"]) > Decimal(base["training"]["cost_usd"])
    assert high["training"]["good"] <= base["training"]["good"]
    assert Decimal(high["development_validation"]["net_usd"]) < Decimal(base["development_validation"]["net_usd"])


def test_sealed_final_holdout_never_used_for_selection_or_trade_outcomes():
    rows = sample()
    first = evaluate(rows)
    changed = list(rows)
    for i in range(1650, len(changed)):
        row = changed[i]
        bump = Decimal("75")
        changed[i] = replace(
            row, open=str(Decimal(row.open) + bump),
            high=str(Decimal(row.high) + bump),
            low=str(Decimal(row.low) + bump),
            close=str(Decimal(row.close) + bump),
        )
    other = evaluate(changed)
    for key in ("batches", "training", "development_validation", "selected_rule",
                "training_max_drawdown_fraction", "hypothetical_outcome_preview"):
        assert first[key] == other[key]
    assert first["scenario_sha256"] != other["scenario_sha256"]


def test_invalid_scope_costs_and_short_history_fail_closed():
    with pytest.raises(CandleStudyError, match="supported"):
        evaluate(allowed_tactics=("scalping",))
    with pytest.raises(CandleStudyError, match="partition refused"):
        evaluate(sample(100))
    with pytest.raises(CandleStudyError, match="bounded research limits"):
        AssumedCosts(full_spread_usd_per_oz=Decimal("-0.25"))
    with pytest.raises(CandleStudyError, match="finite"):
        AssumedCosts(quantity_oz=Decimal("Infinity"))
