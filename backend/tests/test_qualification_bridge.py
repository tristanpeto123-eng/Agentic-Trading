from datetime import datetime, timedelta, timezone

from agentic_trading.qualification_bridge import inspect_historical_csv


def test_bridge_does_not_qualify_unverified_short_history():
    acquired = datetime(2026, 10, 26, tzinfo=timezone.utc)
    content = ("time,open,high,low,close\n"
               "2026-10-23T10:00:00Z,4000,4002,3998,4001\n"
               "2026-10-23T10:15:00Z,4001,4003,3999,4002\n")
    report = inspect_historical_csv(content, acquired, minimum_rows=2)
    assert report["qualification"]["research_eligible"] is False
    assert report["qualification"]["paper_eligible"] is False
    assert report["qualification"]["live_eligible"] is False
    assert report["backtest_performed"] is False
    assert "less than 365 days of historical coverage" in report["qualification"]["issues"]
    assert report["source_sha256"] != report["canonical_sha256"]
