"""Five-batch training-set observation; no trade result or holdout leakage."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from agentic_trading.data_engine import Candle
from agentic_trading.candle_study import CandleStudyError, study_candles


START = datetime(2025, 1, 1, tzinfo=timezone.utc)
SOURCE = "a" * 64


def sample(n=2000):
    rows = []
    for i in range(n):
        close = Decimal("4000") + Decimal(i // 17) / 8 + Decimal(i % 17 - 8) / 5
        opening = close - Decimal("0.14")
        rows.append(Candle(
            open_time=START + timedelta(minutes=i * 15),
            open=str(opening),
            high=str(max(opening, close) + Decimal("0.40")),
            low=str(min(opening, close) - Decimal("0.40")),
            close=str(close),
            volume=None,
        ))
    return rows


def research(rows=None, **kwargs):
    return study_candles(rows if rows is not None else sample(),
                         dataset_id="imported-test-dataset",
                         source_sha256=SOURCE,
                         embargo_bars=24, **kwargs)


def test_five_batch_updates_are_visible_and_holdout_remains_sealed():
    report = research(batch_size=48)
    assert report["market"] == "XAUUSD"
    assert report["mode"] == "historical_directional_observation_only"
    assert report["source_verified"] is False
    assert report["neural_training_performed"] is False
    assert report["trade_execution_performed"] is False
    assert report["net_pnl_usd"] is None
    assert report["paper_trading_enabled"] is False
    assert report["live_trading_enabled"] is False
    assert report["holdout_evaluated"] is False
    assert report["sealed_holdout_bars"] > 0
    assert report["training_bars"] + report["validation_bars"] + report["sealed_holdout_bars"] + 96 == 2000
    batches = report["batches"]
    assert len(batches) > 15
    assert [b["batch"] for b in batches] == list(range(1, len(batches) + 1))
    assert all(b["updated_after"] == (b["batch"] % 5 == 0) for b in batches)
    assert all(b["selector_version"] == ((b["batch"] - 1) // 5 + 1) for b in batches)
    assert report["selector_version"] == 1 + len(batches) // 5
    assert report["development_validation"]["selector_frozen"] is True
    assert report["training"]["observations"] > 0
    assert report["training"]["accuracy_pct"] is not None
    assert report == research(batch_size=48)


def test_changing_sealed_holdout_cannot_change_training_or_validation():
    candles = sample()
    baseline = research(candles)
    altered = sample()
    for i in range(1650, 2000):
        original = Decimal(altered[i].close)
        adjustment = Decimal("20")
        altered[i] = Candle(
            open_time=altered[i].open_time,
            open=str(Decimal(altered[i].open) + adjustment),
            high=str(Decimal(altered[i].high) + adjustment),
            low=str(Decimal(altered[i].low) + adjustment),
            close=str(original + adjustment),
            volume=None,
        )
    changed = research(altered)
    assert changed["batches"] == baseline["batches"]
    assert changed["training"] == baseline["training"]
    assert changed["development_validation"] == baseline["development_validation"]
    assert changed["split_manifest_sha256"] != baseline["split_manifest_sha256"]


def test_gaps_are_skipped_not_interpolated():
    candles = sample()
    shifted = []
    for i, row in enumerate(candles):
        shifted.append(Candle(
            open_time=row.open_time + (timedelta(minutes=30) if i >= 750 else timedelta()),
            open=row.open, high=row.high, low=row.low,
            close=row.close, volume=None))
    report = research(shifted)
    assert any(b["skipped"] > 0 for b in report["batches"])
    assert report["sealed_holdout_bars"] > 0


def test_scope_and_too_short_data_fail_closed():
    narrowed = research(allowed_tactics=("range",))
    assert narrowed["fixed_rules"] == ["range"]
    assert all(b["selected_rule"] == "range" for b in narrowed["batches"])
    with pytest.raises(CandleStudyError, match="supported"):
        research(allowed_tactics=("scalping",))
    with pytest.raises(CandleStudyError, match="partition"):
        research(sample(100))
    with pytest.raises(CandleStudyError, match="Embargo"):
        research(embargo_bars=1)
    with pytest.raises(CandleStudyError, match="batch size"):
        research(batch_size=10)
