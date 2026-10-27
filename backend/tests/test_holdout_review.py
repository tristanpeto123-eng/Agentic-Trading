"""Evaluation fixtures must not be represented as market performance."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from agentic_trading.contracts.common import EvidenceKind
from agentic_trading.simulator import ReplayReport, TradeRecord
from agentic_trading.holdout_review import review_holdout

T = datetime(2025, 4, 7, tzinfo=timezone.utc)
HASH = "a" * 64


def report(trades):
    return ReplayReport(
        evidence_kind=EvidenceKind.SYNTHETIC,
        source_sha256=HASH, configuration_sha256=HASH,
        journal_sha256=HASH, quote_stream_sha256=HASH,
        trades=tuple(trades), ledger_events=(),
        final_equity_usd=Decimal("1000") + sum(
            (t.net_pnl_usd for t in trades if t.net_pnl_usd is not None), Decimal("0")),
        peak_equity_usd=Decimal("1000"), max_drawdown_fraction=Decimal("0"),
        net_pnl_usd=sum((t.net_pnl_usd for t in trades if t.net_pnl_usd is not None), Decimal("0")),
    )


def trade(i, pnl, *, entry_offset=0, exit_offset=1):
    return TradeRecord(
        proposal_id=str(i), status="CLOSED", reason="EXECUTED",
        entry_at=T + timedelta(minutes=i + entry_offset),
        exit_at=T + timedelta(minutes=i + exit_offset),
        entry_fill=Decimal("100"), exit_fill=Decimal("101"),
        quantity_oz=Decimal("1"), gross_pnl_usd=Decimal(str(pnl)),
        commissions_usd=Decimal("0"), net_pnl_usd=Decimal(str(pnl)),
        net_r=Decimal(str(pnl)) / Decimal("2"),
        exit_reason="TIMEOUT",
    )


def test_costed_metrics_are_descriptive_not_authorisation():
    series = [trade(2, 10), trade(4, -2), trade(6, 4)]
    r = review_holdout(report(series), starts_at=T, ends_at=T + timedelta(minutes=10),
                       min_closed_trades=3)
    assert r["closed_trades"] == 3
    assert r["net_pnl_usd"] == "12"
    assert r["profit_factor"] == "7"
    assert r["wins"] == 2 and r["losses"] == 1
    assert r["performance_screen_met"]
    assert not r["holdout_isolation_independently_verified"]
    assert not r["registrar_approved"]
    assert not r["paper_eligible"] and not r["live_eligible"]
    assert review_holdout(report(series), starts_at=T, ends_at=T + timedelta(minutes=10),
                          min_closed_trades=3)["evidence_sha256"] == r["evidence_sha256"]


def test_boundary_crossing_and_unresolved_fail_closed():
    crossing = trade(3, 10, entry_offset=-2, exit_offset=2)
    unresolved = TradeRecord(proposal_id="missing", status="UNRESOLVED",
                             reason="END_OF_TAPE_OPEN_POSITION",
                             entry_at=T + timedelta(minutes=4),
                             entry_fill=Decimal("100"), quantity_oz=Decimal("1"))
    r = review_holdout(report([crossing, unresolved]),
                       starts_at=T + timedelta(minutes=3),
                       ends_at=T + timedelta(minutes=9), min_closed_trades=1)
    assert r["boundary_crossing_trades"] == 1
    assert r["unresolved_trades"] == 1
    assert not r["performance_screen_met"]


def test_no_losses_no_trades_and_bad_window_cannot_pass():
    r = review_holdout(report([trade(2, 10)]), starts_at=T,
                       ends_at=T + timedelta(minutes=5), min_closed_trades=1)
    assert r["profit_factor"] is None
    assert not r["performance_screen_met"]
    empty = review_holdout(report([]), starts_at=T, ends_at=T + timedelta(minutes=5))
    assert empty["win_rate_fraction"] is None
    with pytest.raises(ValueError, match="precede"):
        review_holdout(report([]), starts_at=T, ends_at=T)
    with pytest.raises(ValueError, match="positive"):
        review_holdout(report([]), starts_at=T, ends_at=T + timedelta(minutes=1),
                       min_closed_trades=0)


def test_unresolved_trade_from_before_window_still_blocks():
    unfinished = TradeRecord(proposal_id="prior", status="UNRESOLVED",
                             reason="MISSING_M1_DURING_POSITION",
                             entry_at=T - timedelta(minutes=1),
                             entry_fill=Decimal("100"), quantity_oz=Decimal("1"))
    sample = [unfinished, trade(2, 10), trade(4, -1)]
    r = review_holdout(report(sample), starts_at=T, ends_at=T + timedelta(minutes=7),
                       min_closed_trades=2)
    assert r["unresolved_trades"] == 1
    assert not r["performance_screen_met"]
    assert not r["paper_eligible"]
