"""Independent, research-only scoring of an already costed historical replay.

A performance screen is not an Examiner/Registrar decision. Historical M15 OHLC
cannot be turned into invented M1 bid/ask tape to bypass the replay's fill rules.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json

from agentic_trading.contracts.common import require_utc
from agentic_trading.simulator import ReplayReport, TradeRecord

ZERO = Decimal("0")


def _decimal_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def review_holdout(
    report: ReplayReport,
    *,
    starts_at: datetime,
    ends_at: datetime,
    min_closed_trades: int = 30,
    max_drawdown_fraction: Decimal = Decimal("0.20"),
) -> dict:
    """Score a declared time window, without altering agent or execution permissions.

    The window must be predeclared, externally frozen, and strictly after training.
    Trades crossing its boundary invalidate the screen rather than being cherry-picked.
    A caller's chosen dates alone do not prove out-of-sample isolation.
    """
    require_utc(starts_at)
    require_utc(ends_at)
    if starts_at >= ends_at:
        raise ValueError("Holdout start must precede end")
    if min_closed_trades < 1:
        raise ValueError("min_closed_trades must be positive")
    limit = Decimal(str(max_drawdown_fraction))
    if not ZERO < limit < Decimal("1"):
        raise ValueError("max_drawdown_fraction must be between zero and one")

    indexed: list[tuple[datetime, TradeRecord]] = []
    unresolved = 0
    boundary_crossing = 0
    for trade in report.trades:
        if trade.status == "REJECTED":
            continue
        if trade.entry_at is None:
            raise ValueError("Filled trade is missing its entry time")
        require_utc(trade.entry_at)
        if trade.status == "UNRESOLVED":
            if starts_at <= trade.entry_at < ends_at:
                unresolved += 1
            continue
        if trade.exit_at is None or trade.net_pnl_usd is None:
            raise ValueError("Closed trade is missing its exit or costed P&L")
        require_utc(trade.exit_at)
        if trade.exit_at < trade.entry_at:
            raise ValueError("Trade exits before entry")
        # Exclude training-period trades closed in holdout and trades left open
        # across the end boundary. Both are recorded as isolation violations.
        if (trade.entry_at < starts_at <= trade.exit_at
                or starts_at <= trade.entry_at < ends_at < trade.exit_at):
            boundary_crossing += 1
        if starts_at <= trade.entry_at < ends_at and trade.exit_at <= ends_at:
            indexed.append((trade.exit_at, trade))

    indexed.sort(key=lambda value: (value[0], value[1].proposal_id))
    pnl = [trade.net_pnl_usd for _, trade in indexed]
    wins = [value for value in pnl if value > ZERO]
    losses = [value for value in pnl if value < ZERO]
    count = len(pnl)
    net = sum(pnl, ZERO)
    gross_profit = sum(wins, ZERO)
    gross_loss = -sum(losses, ZERO)
    # ReplayReport's starting equity is final minus its global booked P&L.
    starting_equity = report.final_equity_usd - report.net_pnl_usd
    if starting_equity <= ZERO:
        raise ValueError("Replay's reconstructed starting equity is invalid")
    equity = starting_equity
    peak = equity
    drawdown = ZERO
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    profit_factor = gross_profit / gross_loss if gross_loss else None
    warnings = [
        "This is descriptive historical research, not independently certified out-of-sample performance.",
        "Price data, costs, strategy freeze, and provider rights require separate independent verification.",
    ]
    if not count:
        warnings.append("No closed trades in the selected holdout")
    if unresolved:
        warnings.append("Unresolved holdout trades; results are incomplete")
    if boundary_crossing:
        warnings.append("Trades crossed the holdout boundary")
    if profit_factor is None:
        warnings.append("Profit factor undefined without losing trades")
    performance_screen_met = (
        count >= min_closed_trades
        and net > ZERO and gross_loss > ZERO and profit_factor is not None
        and profit_factor > Decimal("1")
        and drawdown <= limit
        and unresolved == 0 and boundary_crossing == 0
    )
    window = {"starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat()}
    evidence = {
        "replay_journal_sha256": report.journal_sha256,
        "quote_stream_sha256": report.quote_stream_sha256,
        "source_sha256": report.source_sha256,
        "configuration_sha256": report.configuration_sha256,
        "evidence_kind": report.evidence_kind.value,
        "window": window,
    }
    evidence_digest = sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version": "holdout_research_review.v1",
        "evidence": evidence,
        "evidence_sha256": evidence_digest,
        "closed_trades": count,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": count - len(wins) - len(losses),
        "unresolved_trades": unresolved,
        "boundary_crossing_trades": boundary_crossing,
        "net_pnl_usd": _decimal_str(net),
        "gross_profit_usd": _decimal_str(gross_profit),
        "gross_loss_usd": _decimal_str(gross_loss),
        "win_rate_fraction": _decimal_str(Decimal(len(wins)) / count) if count else None,
        "expectancy_usd_per_trade": _decimal_str(net / count) if count else None,
        "profit_factor": _decimal_str(profit_factor),
        "maximum_drawdown_fraction": _decimal_str(drawdown),
        "performance_screen_met": performance_screen_met,
        "holdout_isolation_independently_verified": False,
        "registrar_approved": False,
        "paper_eligible": False,
        "live_eligible": False,
        "warnings": warnings,
    }
