"""Regression: M1 quote-side scenario must never imply an executable fill."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from replay_xauusd_m1_pair import replay_bid_ask, ReplayError

START = datetime(2026, 10, 28, tzinfo=timezone.utc)


def write(path, *, ask=False, gaps=(), crossed_open=False, slope="0.25"):
    rows = ["Etc/UTC,Open,High,Low,Close,Volume\n"]
    for i in range(45):
        if i in gaps:
            continue
        op = Decimal("4000") + Decimal(str(i)) * Decimal(slope)
        if ask:
            op += Decimal("0.6")
        if crossed_open and ask and i == 12:
            op -= Decimal("2")
        cl = op + Decimal("0.1")
        high = max(op, cl) + Decimal("0.2")
        low = min(op, cl) - Decimal("0.2")
        stamp = (START + timedelta(minutes=i)).isoformat()
        rows.append(f"{stamp},{op},{high},{low},{cl},100\n")
    path.write_text("".join(rows), encoding="utf-8")
    return path


def pair(tmp_path, *, gaps=(), crossed_open=False, slope="0.25"):
    bid = write(tmp_path / "bid.csv", gaps=gaps, slope=slope)
    ask = write(tmp_path / "ask.csv", ask=True, gaps=gaps,
                crossed_open=crossed_open, slope=slope)
    return bid, ask


def test_crosses_actual_quote_sides_with_extra_costs_and_latency(tmp_path):
    report = replay_bid_ask(*pair(tmp_path), lookback=2, holding=2,
                            latency=1, threshold=Decimal("0.1"),
                            quantity=Decimal("1"), commission=Decimal("0.05"),
                            slippage=Decimal("0.1"))
    trade = report["first_trade_examples"][0]
    assert trade["direction"] == "LONG"
    assert trade["signal_known_at_utc"] == (START + timedelta(minutes=3)).isoformat()
    assert trade["entry_open_utc"] == (START + timedelta(minutes=4)).isoformat()
    assert trade["exit_open_utc"] == (START + timedelta(minutes=6)).isoformat()
    # ASK in at 4001.6, BID out at 4001.5. Spread already paid.
    assert Decimal(trade["hypothetical_gross_usd"]) == Decimal("-0.1")
    assert Decimal(trade["additional_assumed_cost_usd"]) == Decimal("0.30")
    assert Decimal(trade["hypothetical_net_usd"]) == Decimal("-0.40")
    assert report["outcomes"]["negative_net"] == report["outcomes"]["closed_hypothetical_trades"]
    assert report["skips"]["overlapping_position"] > 0
    assert not report["actual_fills_or_realised_profitability_proven"]
    assert not report["broker_execution_enabled"]
    assert not report["independent_holdout_or_model_qualification"]


def test_short_enters_bid_exits_ask(tmp_path):
    report = replay_bid_ask(*pair(tmp_path, slope="-0.25"),
                            lookback=2, holding=2, latency=1,
                            threshold=Decimal("0.1"), quantity=Decimal("1"),
                            commission=Decimal("0"), slippage=Decimal("0"))
    trade = report["first_trade_examples"][0]
    assert trade["direction"] == "SHORT"
    assert Decimal(trade["hypothetical_gross_usd"]) == Decimal("-0.1")
    assert not report["paper_trading_eligible"]


def test_missing_minutes_are_never_filled_or_traded_across(tmp_path):
    report = replay_bid_ask(*pair(tmp_path, gaps=(15, 16, 17)),
                            lookback=2, holding=3, latency=1,
                            threshold=Decimal("0.1"))
    assert report["skips"]["noncontiguous_quotes"] > 0
    for trade in report["first_trade_examples"]:
        enter = datetime.fromisoformat(trade["entry_open_utc"])
        leave = datetime.fromisoformat(trade["exit_open_utc"])
        assert leave - enter == timedelta(minutes=3)


def test_crossed_open_rejected_even_if_closing_spread_is_positive(tmp_path):
    b, a = pair(tmp_path, crossed_open=True)
    # Make one anomalous ASK open but a positive close spread and valid OHLC.
    with pytest.raises(ReplayError, match="opening spread"):
        replay_bid_ask(b, a)


@pytest.mark.parametrize("params", [
    {"latency": 0}, {"lookback": 1}, {"holding": 0},
    {"threshold": Decimal("-1")}, {"quantity": Decimal("0")},
    {"quantity": Decimal("1.01")}, {"commission": Decimal("-1")},
    {"slippage": Decimal("NaN")}, {"holding": True},
])
def test_unsafe_assumptions_fail_closed(tmp_path, params):
    with pytest.raises(ReplayError):
        replay_bid_ask(*pair(tmp_path), **params)


def test_flat_series_abstains_and_never_claims_performance(tmp_path):
    report = replay_bid_ask(*pair(tmp_path, slope="0"),
                            lookback=2, holding=2, threshold=Decimal("0.1"))
    assert report["outcomes"]["closed_hypothetical_trades"] == 0
    assert report["outcomes"]["win_rate_pct"] is None
    assert report["outcomes"]["hypothetical_net_usd"] == "0"
    assert report["first_trade_examples"] == []
