from datetime import datetime, timezone
from pathlib import Path

from agentic_trading.data_engine import DataQualityError
from agentic_trading.qualification_bridge import inspect_historical_csv


def test_offline_audit_explicitly_blocks_trading():
    content = ("time,open,high,low,close\n"
               "2026-10-23T10:00:00Z,4000,4002,3998,4001\n"
               "2026-10-23T10:15:00Z,4001,4003,3999,4002\n")
    report = inspect_historical_csv(
        content, datetime(2026, 10, 24, tzinfo=timezone.utc),
        minimum_rows=2, provenance_verified=True, rights_verified=True,
    )
    assert report["qualification"]["research_eligible"] is False
    assert report["qualification"]["independent_source_verification_required"] is True
    assert report["qualification"]["paper_eligible"] is False
    assert report["qualification"]["live_eligible"] is False
    assert report["registrar_approved"] is False
    assert "less than 365 days of historical coverage" in report["qualification"]["issues"]
