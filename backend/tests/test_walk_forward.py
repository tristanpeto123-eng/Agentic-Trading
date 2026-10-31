from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from agentic_trading.walk_forward import (
    WalkForwardError, plan_walk_forward, verify_walk_forward_manifest,
)

T = datetime(2025, 1, 1, tzinfo=timezone.utc)


def candles(n=2000):
    return [SimpleNamespace(open_time=T+timedelta(minutes=i), open="2000",
                            high="2001", low="1999", close="2000", volume=1)
            for i in range(n)]


def plan(data=None):
    return plan_walk_forward(
        candles() if data is None else data,
        min_train=400, validation_bars=120, step_bars=120,
        embargo_bars=30, sealed_test_bars=300,
    )


def test_expanding_folds_isolated_from_final_sealed_window():
    p = plan()
    assert p.research_only and not p.qualified and not p.independent_evidence_verified
    assert p.manifest_sha256 == plan().manifest_sha256
    m = p.manifest
    assert m["sealed_test"]["start"] == 1700
    assert m["development_end_exclusive"] == 1670
    assert not m["sealed_test"]["accessible_to_development"]
    assert len(m["folds"]) >= 3
    previous = 0
    for fold in m["folds"]:
        tr, dev = fold["train"], fold["validation"]
        assert tr["end_exclusive"] + 30 == dev["start"]
        assert dev["end_exclusive"] <= 1670
        assert tr["end_exclusive"] >= previous
        previous = tr["end_exclusive"]
    assert verify_walk_forward_manifest(candles(), p)


def test_changed_prices_fail_frozen_manifest():
    original = plan()
    altered = candles()
    altered[-1].close = "2000.5"
    with pytest.raises(WalkForwardError, match="does not match"):
        verify_walk_forward_manifest(altered, original)


def test_no_valid_folds_if_history_too_short():
    with pytest.raises(WalkForwardError, match="insufficient history"):
        plan(candles(700))


def test_no_invalid_settings_or_boolean_sizes():
    with pytest.raises(WalkForwardError, match="fold sizes"):
        plan_walk_forward(candles(), min_train=True, validation_bars=120,
                          step_bars=120, embargo_bars=30, sealed_test_bars=300)
    with pytest.raises(WalkForwardError, match="step cannot exceed"):
        plan_walk_forward(candles(), min_train=400, validation_bars=100,
                          step_bars=101, embargo_bars=30, sealed_test_bars=300)


@pytest.mark.parametrize(("field", "value"), [
    ("close", "-1"), ("low", "3000"), ("volume", "-1"),
])
def test_bad_candles_in_sealed_window_fail_closed(field, value):
    data = candles()
    setattr(data[-1], field, value)
    with pytest.raises(WalkForwardError, match="invalid candle"):
        plan(data)


def test_no_out_of_order_or_unaware_timestamps():
    data = candles()
    data[-1].open_time = data[-2].open_time
    with pytest.raises(WalkForwardError, match="strictly increasing"):
        plan(data)
    data = candles()
    data[-1].open_time = data[-1].open_time.replace(tzinfo=None)
    with pytest.raises(WalkForwardError, match="invalid candle"):
        plan(data)
