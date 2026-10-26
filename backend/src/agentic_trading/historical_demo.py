"""Synthetic-only historical engine demonstration for the authenticated CEO preview.

Uses the existing conservative M1 bid/ask replay engine. The fixture is deliberately
manufactured and its signals are fixed in advance, not learned/model-generated.
No dataset import, broker, exam, student update, qualification or trading occurs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from agentic_trading.contracts.common import EvidenceKind
from agentic_trading.contracts.trading import TradeProposal, TradeAssessment, GuardianDecision
from agentic_trading.simulator import QuoteBar, ReplayCosts, HistoricalOrder, replay


START = datetime(2025, 4, 7, 9, 0, tzinfo=timezone.utc)
MINUTE = timedelta(minutes=1)
QUOTE_SPREAD = Decimal("0.20")
FIXTURE_LABEL = "SYNTHETIC_ONLY__NOT_REAL_MARKET_OR_MODEL_PERFORMANCE"


def _mid(i: int) -> Decimal:
    """Deterministic sawtooth + drift: a test fixture, NOT a price forecast."""
    return (Decimal("2000") + Decimal(i) * Decimal("0.035")
            + Decimal(i % 32 - 16) * Decimal("0.11")
            + Decimal((i * 7) % 13 - 6) * Decimal("0.05")).quantize(Decimal("0.01"))


def _bar(i: int) -> QuoteBar:
    opening = _mid(max(0, i - 1))
    closing = _mid(i)
    high = max(opening, closing) + Decimal("0.25")
    low = min(opening, closing) - Decimal("0.25")
    return QuoteBar(
        open_time=START + i * MINUTE,
        bid_open=opening, bid_high=high, bid_low=low, bid_close=closing,
        ask_open=opening + QUOTE_SPREAD, ask_high=high + QUOTE_SPREAD,
        ask_low=low + QUOTE_SPREAD, ask_close=closing + QUOTE_SPREAD,
    )


def _order(n: int, index: int) -> HistoricalOrder:
    seen = START + (index + 1) * MINUTE  # The signal can only use a CLOSED bar.
    reference = _mid(index)
    direction = "LONG" if n % 2 == 0 else "SHORT"
    pid = UUID(f"00000000-0000-4000-8000-{n + 1:012d}")
    uid = UUID("00000000-0000-4000-8000-000000009999")
    stop = reference + (Decimal("-2.50") if direction == "LONG" else Decimal("2.50"))
    target = reference + (Decimal("2.50") if direction == "LONG" else Decimal("-2.50"))
    proposal = TradeProposal(
        proposal_id=pid, revision=1, student_id=uid,
        strategy_version="synthetic-ui-fixture-v1", model_sha256="a" * 64,
        instrument="XAUUSD", direction=direction, entry_reference=reference,
        stop_price=stop, target_price=target, tactic_id="fixture",
        thesis="Fixed synthetic demo signal; not learned", invalidation="Fixture stop",
        observed_data_available_at=seen, created_at=seen,
        expires_at=seen + timedelta(minutes=5), content_sha256="b" * 64,
    )
    assessment = TradeAssessment(
        proposal_id=pid, proposal_revision=1, proposal_sha256="b" * 64,
        scout_b_model_sha256="a" * 64, expected_net_r="0.25",
        assessed_at=seen + timedelta(seconds=1),
    )
    guardian = GuardianDecision(
        proposal_id=pid, proposal_revision=1, proposal_sha256="b" * 64,
        decision="APPROVED", reasons=("Synthetic replay fixture only",),
        decided_at=seen + timedelta(seconds=2),
    )
    return HistoricalOrder(
        proposal=proposal, assessment=assessment, guardian=guardian,
        quantity_oz=Decimal("2"),
    )


def build_historical_demo() -> dict:
    bars = tuple(_bar(i) for i in range(180))
    orders = tuple(_order(n, i) for n, i in enumerate((8, 40, 72, 104, 136)))
    costs = ReplayCosts(
        commission_usd_per_oz_per_side="0.05",
        slippage_usd_per_oz_per_side="0.10",
        max_spread_usd_per_oz="0.50",
        starting_equity_usd="10000",
        max_position_oz="10",
        max_risk_fraction="0.05",
        max_leverage="2",
        max_holding_minutes=14,
    )
    source_digest = sha256(b"agentic-2026-ui-synthetic-fixture-m1-v1").hexdigest()
    report = replay(
        bars=bars, orders=orders, costs=costs,
        evidence_kind=EvidenceKind.SYNTHETIC,
        source_sha256=source_digest,
        as_of=START + 180 * MINUTE,
    )
    results = [t for t in report.trades if t.status == "CLOSED"]
    wins = sum(1 for t in results if t.net_pnl_usd is not None and t.net_pnl_usd > 0)
    losses = sum(1 for t in results if t.net_pnl_usd is not None and t.net_pnl_usd < 0)
    directions = {str(order.proposal.proposal_id): order.proposal.direction.value for order in orders}
    trade_rows = [
        {**r.model_dump(mode="json"), "direction": directions[r.proposal_id]}
        for r in report.trades
    ]
    change_events = sorted(
        [(t.exit_at, t.net_pnl_usd) for t in results if t.exit_at is not None
         and t.net_pnl_usd is not None],
        key=lambda value: value[0],
    )
    current_equity = costs.starting_equity_usd
    cumulative = 0
    equity_curve = []
    for bar in bars:
        now = bar.open_time + MINUTE
        while cumulative < len(change_events) and change_events[cumulative][0] <= now:
            current_equity += change_events[cumulative][1]
            cumulative += 1
        equity_curve.append({
            "time": now.isoformat().replace("+00:00", "Z"),
            "equity": str(current_equity),
        })
    return {
        "market": "XAUUSD", "timeframe": "M1",
        "fixture": FIXTURE_LABEL,
        "synthetic": True, "student_model_generated": False,
        "qualification_eligible": False, "paper_trading_enabled": False,
        "live_trading_enabled": False, "historical_demo_available": True,
        "warnings": [
            "Invented M1 bid/ask candles: NOT a historical market dataset.",
            "Fixed demonstration proposals: NOT produced by a trained student.",
            "Net P&L is computed by the conservative replay engine but is NOT an investable performance result.",
        ],
        "prices": [
            {"time": b.open_time.isoformat().replace("+00:00", "Z"),
             "close": str(b.bid_close)} for b in bars
        ],
        "equity": equity_curve,
        "trades": trade_rows,
        "metrics": {
            "starting_equity_usd": str(costs.starting_equity_usd),
            "ending_equity_usd": str(report.final_equity_usd),
            "net_pnl_usd": str(report.net_pnl_usd),
            "max_drawdown_fraction": str(report.max_drawdown_fraction),
            "win_rate_pct": str(Decimal(100) * wins / len(results)) if results else "0",
            "closed": len(results), "wins": wins, "losses": losses,
            "rejected": sum(1 for t in report.trades if t.status == "REJECTED"),
            "unresolved": sum(1 for t in report.trades if t.status == "UNRESOLVED"),
            "journal_sha256": report.journal_sha256,
        },
    }
