from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from agentic_trading.qualification import assess_candles


def candles(n=10):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        SimpleNamespace(open_time=start + timedelta(minutes=15 * i),
                        open=100, high=102, low=99, close=101)
        for i in range(n)
    ]


def test_unverified_never_qualifies_or_enables_trading():
    report = assess_candles(candles(), minimum_rows=10)
    assert not report.research_eligible
    assert not report.paper_eligible
    assert not report.live_eligible
    assert "source provenance unverified" in report.issues
    assert "data rights unverified" in report.issues


def test_valid_data_screen_never_grants_research_or_trading_eligibility():
    report = assess_candles(candles(), minimum_rows=10,
                            provenance_verified=True, rights_verified=True)
    assert report.data_screen_passed
    assert not report.research_eligible
    assert (report.train_rows, report.validation_rows, report.test_rows) == (6, 2, 2)
    assert not report.paper_eligible and not report.live_eligible
    assert report.dataset_sha256 == assess_candles(candles(), minimum_rows=10).dataset_sha256


def test_duplicate_or_bad_ohlc_fails_closed():
    sample = candles()
    sample[3].open_time = sample[2].open_time
    sample[4].high = 90
    report = assess_candles(sample, minimum_rows=10,
                            provenance_verified=True, rights_verified=True)
    assert not report.research_eligible
    assert any("strictly increase" in issue for issue in report.issues)
    assert any("OHLC" in issue for issue in report.issues)
