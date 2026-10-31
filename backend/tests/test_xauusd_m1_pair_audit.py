"""Local-only M1 quote audit never confers data rights or trading authority."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from audit_xauusd_m1_pair import audit_bid_ask, QuoteAuditError

STAMP = datetime(2026, 10, 28, 0, tzinfo=timezone.utc)


def write(path, *, side, shift=0, bad=None):
    fields = "Etc/UTC,Open,High,Low,Close,Volume\n"
    records = []
    for i in range(3):
        at = STAMP + timedelta(minutes=i + shift)
        delta = 1 if side == "ask" else 0
        vals = [4000 + i + delta, 4002 + i + delta,
                3998 + i + delta, 4001 + i + delta, 20]
        if bad == "ohlc" and i == 1:
            vals[1] = 1
        if bad == "negative_spread" and i == 1:
            vals[3] -= 10
        records.append(at.isoformat() + "," + ",".join(map(str, vals)) + "\n")
    path.write_text(fields + "".join(records))
    return path


def test_matches_and_independent_rights_remain_unverified(tmp_path):
    b = write(tmp_path / "bid.csv", side="bid")
    a = write(tmp_path / "ask.csv", side="ask")
    report = audit_bid_ask(b, a)
    assert report["aligned_m1_rows"] == 3
    assert report["alignment_fraction"] == "1.000000"
    assert report["close_spread_usd_per_oz"]["median"] == "1"
    assert report["bid"]["gaps_require_session_calendar_review"] is False
    assert not report["source_authenticity_independently_verified"]
    assert not report["data_usage_rights_independently_verified"]
    assert not report["historical_coverage_requirement_met"]
    assert not report["paper_trading_eligible"]


def test_detects_missing_bid_rows_without_fabricating_quotes(tmp_path):
    b = write(tmp_path / "bid.csv", side="bid", shift=1)
    a = write(tmp_path / "ask.csv", side="ask")
    report = audit_bid_ask(b, a)
    assert report["aligned_m1_rows"] == 2
    assert report["bid_only_rows"] == 1
    assert report["ask_only_rows"] == 1


@pytest.mark.parametrize(("side", "bad"), [
    ("ask", "ohlc"),
    ("ask", "negative_spread"),
])
def test_invalid_ohlc_or_spread_is_rejected(tmp_path, side, bad):
    b = write(tmp_path / "bid.csv", side="bid",
              bad=bad if side == "bid" else None)
    a = write(tmp_path / "ask.csv", side="ask",
              bad=bad if side == "ask" else None)
    with pytest.raises(QuoteAuditError):
        audit_bid_ask(b, a)


def test_rejects_duplicate_timestamp_and_naive_clock(tmp_path):
    b = write(tmp_path / "bid.csv", side="bid")
    a = write(tmp_path / "ask.csv", side="ask")
    data = b.read_text().splitlines()
    b.write_text("\n".join(data + [data[-1]]) + "\n")
    with pytest.raises(QuoteAuditError, match="duplicate"):
        audit_bid_ask(b, a)
    b.write_text("\n".join(data) + "\n")
    b.write_text(b.read_text().replace("+00:00", ""))
    with pytest.raises(QuoteAuditError, match="not UTC"):
        audit_bid_ask(b, a)
