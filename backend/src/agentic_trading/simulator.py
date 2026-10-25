"""Sprint 3 historical-only, deterministic bid/ask M1 replay.

Pure, offline research module: NO execution API or broker connectivity.
Unverified/synthetic fixture results can never qualify models or students.
No candles, synthetic prices, fills, or future observations are manufactured.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agentic_trading.contracts.common import EvidenceKind, FrozenModel, Sha256, require_utc
from agentic_trading.contracts.trading import GuardianDecision, TradeAssessment, TradeProposal
from agentic_trading.policy import research_execution_authorised

MINUTE = timedelta(minutes=1)
ZERO = Decimal("0")


class ReplayError(ValueError):
    """Reject invalid or incomplete historical execution input without guessing."""


class QuoteBar(FrozenModel):
    """One closed minute, with independently observed bid and ask OHLC."""
    open_time: datetime
    bid_open: Decimal = Field(gt=0)
    bid_high: Decimal = Field(gt=0)
    bid_low: Decimal = Field(gt=0)
    bid_close: Decimal = Field(gt=0)
    ask_open: Decimal = Field(gt=0)
    ask_high: Decimal = Field(gt=0)
    ask_low: Decimal = Field(gt=0)
    ask_close: Decimal = Field(gt=0)

    @field_validator("open_time")
    @classmethod
    def utc_minute(cls, value: datetime) -> datetime:
        require_utc(value)
        if value.second or value.microsecond:
            raise ValueError("M1 timestamps must begin at whole UTC minutes")
        return value

    @model_validator(mode="after")
    def validate_quotes(self):
        for side in ("bid", "ask"):
            op, hi, lo, cl = (getattr(self, f"{side}_{part}") for part in ("open", "high", "low", "close"))
            if hi < max(op, lo, cl) or lo > min(op, hi, cl):
                raise ValueError(f"Invalid {side} OHLC")
        if self.bid_open > self.ask_open or self.bid_close > self.ask_close:
            raise ValueError("Crossed opening or closing quotes")
        return self


class ReplayCosts(FrozenModel):
    """Fixed reproducible costs per troy ounce, denominated in USD."""
    commission_usd_per_oz_per_side: Decimal = Field(ge=0)
    slippage_usd_per_oz_per_side: Decimal = Field(ge=0)
    max_spread_usd_per_oz: Decimal = Field(gt=0)
    starting_equity_usd: Decimal = Field(gt=0)
    max_position_oz: Decimal = Field(gt=0)
    max_risk_fraction: Decimal = Field(gt=0, le=Decimal("0.05"))
    max_leverage: Decimal = Field(gt=0, le=Decimal("20"))
    max_holding_minutes: int = Field(ge=1, le=10_080)


class HistoricalOrder(FrozenModel):
    """Frozen proposal + assessment + Guardian approval, bound by revisions and hashes."""
    proposal: TradeProposal
    assessment: TradeAssessment
    guardian: GuardianDecision
    quantity_oz: Decimal = Field(gt=0)


class TradeRecord(FrozenModel):
    proposal_id: str
    status: Literal["CLOSED", "REJECTED", "UNRESOLVED"]
    reason: str
    entry_at: datetime | None = None
    exit_at: datetime | None = None
    entry_fill: Decimal | None = None
    exit_fill: Decimal | None = None
    quantity_oz: Decimal | None = None
    gross_pnl_usd: Decimal | None = None
    commissions_usd: Decimal | None = None
    net_pnl_usd: Decimal | None = None
    net_r: Decimal | None = None
    ambiguity: bool = False
    exit_reason: str | None = None


class LedgerEvent(FrozenModel):
    event_type: Literal["REJECTED", "ENTRY", "EXIT", "UNRESOLVED"]
    proposal_id: str
    occurred_at: datetime
    price: Decimal | None = None
    quantity_oz: Decimal | None = None
    commission_usd: Decimal = ZERO
    reason: str


class ReplayReport(FrozenModel):
    schema_version: Literal["historical_replay.v1"] = "historical_replay.v1"
    evidence_kind: EvidenceKind
    source_sha256: Sha256
    configuration_sha256: Sha256
    journal_sha256: Sha256
    quote_stream_sha256: Sha256
    qualification_eligible: Literal[False] = False
    execution_model: Literal["m1_bid_ask_conservative_v1"] = "m1_bid_ask_conservative_v1"
    trades: tuple[TradeRecord, ...]
    ledger_events: tuple[LedgerEvent, ...]
    final_equity_usd: Decimal
    peak_equity_usd: Decimal
    max_drawdown_fraction: Decimal
    net_pnl_usd: Decimal


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _valid_tape(bars: tuple[QuoteBar, ...]) -> None:
    if not bars:
        raise ReplayError("A nonempty M1 bid/ask quote tape is required")
    for before, after in zip(bars, bars[1:]):
        if before.open_time >= after.open_time:
            raise ReplayError("Bars must be strictly chronological without duplicates")


def _rejected(order: HistoricalOrder, reason: str) -> TradeRecord:
    return TradeRecord(proposal_id=str(order.proposal.proposal_id), status="REJECTED", reason=reason)


def _unresolved(order: HistoricalOrder, reason: str, *, entry: QuoteBar, price: Decimal) -> TradeRecord:
    return TradeRecord(proposal_id=str(order.proposal.proposal_id), status="UNRESOLVED",
                       reason=reason, entry_at=entry.open_time, entry_fill=price,
                       quantity_oz=order.quantity_oz)


def replay(
    *,
    bars: tuple[QuoteBar, ...],
    orders: tuple[HistoricalOrder, ...],
    costs: ReplayCosts,
    evidence_kind: EvidenceKind,
    source_sha256: Sha256,
    as_of: datetime,
) -> ReplayReport:
    """Conservative deterministic single-position replay of guarded historical orders.

    Orders fill at first eligible M1 open at/after Guardian decision. Long buys ask and
    sells bid; short sells bid and buys ask. Stops take priority if both stop and
    target touch the same M1 bar. Missing M1 while exposed causes UNRESOLVED,
    never a profitable manufactured fill. Qualified data still requires further
    independent Examiner approval; this flag is only a necessary data-integrity gate.
    """
    require_utc(as_of)
    _valid_tape(bars)
    if bars[-1].open_time + MINUTE > as_of:
        raise ReplayError("The replay cannot inspect an unfinished or future M1 candle")
    if len({o.proposal.proposal_id for o in orders}) != len(orders):
        raise ReplayError("Duplicate proposal IDs; replay cannot execute the same instruction twice")
    if tuple(sorted(orders, key=lambda o: (o.guardian.decided_at, str(o.proposal.proposal_id)))) != orders:
        raise ReplayError("Orders must be sorted by Guardian decision time and ID")

    equity = costs.starting_equity_usd
    peak = equity
    drawdown = ZERO
    journal: list[TradeRecord] = []
    busy_until: datetime | None = None
    used_bars = list(bars)
    for order in orders:
        p = order.proposal
        if p.instrument != "XAUUSD":
            journal.append(_rejected(order, "UNSUPPORTED_INSTRUMENT")); continue
        if not research_execution_authorised(p, order.assessment, order.guardian):
            journal.append(_rejected(order, "GUARDIAN_OR_SCOUT_B_NOT_VALID")); continue
        if order.guardian.decided_at < p.observed_data_available_at:
            journal.append(_rejected(order, "FUTURE_SIGNAL")); continue
        if busy_until is not None and order.guardian.decided_at < busy_until:
            journal.append(_rejected(order, "OVERLAPPING_POSITION")); continue
        if order.quantity_oz > costs.max_position_oz:
            journal.append(_rejected(order, "MAX_POSITION_SIZE")); continue
        selected = next((bar for bar in used_bars if bar.open_time >= order.guardian.decided_at
                         and bar.open_time < p.expires_at), None)
        if selected is None:
            journal.append(_rejected(order, "NO_ELIGIBLE_ENTRY_BAR")); continue
        # Never backfill a decision made in the middle of a minute at that minute's open.
        long = p.direction.value == "LONG"
        spread = selected.ask_open - selected.bid_open
        if spread > costs.max_spread_usd_per_oz:
            journal.append(_rejected(order, "SPREAD_LIMIT")); continue
        slip = costs.slippage_usd_per_oz_per_side
        commission = costs.commission_usd_per_oz_per_side * order.quantity_oz * 2
        entry_price = selected.ask_open + slip if long else selected.bid_open - slip
        if entry_price <= ZERO:
            journal.append(_rejected(order, "INVALID_EXECUTED_PRICE")); continue
        distance = (entry_price - p.stop_price if long else p.stop_price - entry_price)
        target_distance = (p.target_price - entry_price if long else entry_price - p.target_price)
        if distance <= ZERO or target_distance <= ZERO:
            journal.append(_rejected(order, "STOP_TARGET_INVALID_AT_FILL")); continue
        risk_usd = distance * order.quantity_oz + slip * order.quantity_oz + commission
        if risk_usd > equity * costs.max_risk_fraction:
            journal.append(_rejected(order, "RISK_LIMIT")); continue
        if entry_price * order.quantity_oz > equity * costs.max_leverage:
            journal.append(_rejected(order, "LEVERAGE_LIMIT")); continue
        earliest_close = selected.open_time + MINUTE
        bar_idx = used_bars.index(selected)
        last_time = selected.open_time - MINUTE
        finished = False
        for bar in used_bars[bar_idx:]:
            if bar.open_time != last_time + MINUTE:
                journal.append(_unresolved(order, "MISSING_M1_DURING_POSITION", entry=selected, price=entry_price))
                busy_until = as_of
                finished = True
                break
            last_time = bar.open_time
            if long:
                stop_hit = bar.bid_low <= p.stop_price
                target_hit = bar.bid_high >= p.target_price
            else:
                stop_hit = bar.ask_high >= p.stop_price
                target_hit = bar.ask_low <= p.target_price
            time_up = bar.open_time + MINUTE >= selected.open_time + timedelta(minutes=costs.max_holding_minutes)
            final_bar = bar == used_bars[-1]
            if not (stop_hit or target_hit or time_up or final_bar):
                continue
            ambiguous = stop_hit and target_hit
            if stop_hit:
                # Worse stop fill on gap through, never optimistic stop improvement.
                price = min(p.stop_price, bar.bid_open) if long else max(p.stop_price, bar.ask_open)
                reason = "STOP_PRIORITY_AMBIGUOUS" if ambiguous else "STOP"
            elif target_hit:
                price = p.target_price  # No favourable gap-through target windfall.
                reason = "TARGET"
            elif time_up:
                price = bar.bid_close if long else bar.ask_close
                reason = "TIMEOUT"
            else:
                journal.append(_unresolved(order, "END_OF_TAPE_OPEN_POSITION", entry=selected, price=entry_price))
                busy_until = as_of
                finished = True
                break
            exit_fill = price - slip if long else price + slip
            gross = (exit_fill - entry_price if long else entry_price - exit_fill) * order.quantity_oz
            net = gross - commission
            record = TradeRecord(proposal_id=str(p.proposal_id), status="CLOSED", reason="EXECUTED",
                                 entry_at=selected.open_time, exit_at=bar.open_time + MINUTE,
                                 entry_fill=entry_price, exit_fill=exit_fill, quantity_oz=order.quantity_oz,
                                 gross_pnl_usd=gross, commissions_usd=commission, net_pnl_usd=net,
                                 net_r=net / risk_usd, ambiguity=ambiguous, exit_reason=reason)
            equity += net
            peak = max(peak, equity)
            drawdown = max(drawdown, (peak - equity) / peak)
            journal.append(record)
            busy_until = bar.open_time + MINUTE
            finished = True
            break
        if not finished:
            journal.append(_unresolved(order, "NO_EXIT_DATA", entry=selected, price=entry_price))
            busy_until = as_of
    # A caller-supplied provenance label or source hash never proves licensing or independent verification.
    # Sprint 7 Examiner alone may issue qualification-eligible evidence after S2 verification.
    ledger: list[LedgerEvent] = []
    by_id = {str(order.proposal.proposal_id): order for order in orders}
    for item in journal:
        order = by_id[item.proposal_id]
        if item.status == "REJECTED":
            ledger.append(LedgerEvent(event_type="REJECTED", proposal_id=item.proposal_id,
                                      occurred_at=order.guardian.decided_at, reason=item.reason))
            continue
        ledger.append(LedgerEvent(event_type="ENTRY", proposal_id=item.proposal_id,
                                  occurred_at=item.entry_at, price=item.entry_fill,
                                  quantity_oz=item.quantity_oz,
                                  commission_usd=costs.commission_usd_per_oz_per_side * item.quantity_oz,
                                  reason="NEXT_ELIGIBLE_M1_OPEN"))
        if item.status == "UNRESOLVED":
            ledger.append(LedgerEvent(event_type="UNRESOLVED", proposal_id=item.proposal_id,
                                      occurred_at=as_of, reason=item.reason))
            continue
        ledger.append(LedgerEvent(event_type="EXIT", proposal_id=item.proposal_id,
                                  occurred_at=item.exit_at, price=item.exit_fill,
                                  quantity_oz=item.quantity_oz,
                                  commission_usd=costs.commission_usd_per_oz_per_side * item.quantity_oz,
                                  reason=item.exit_reason))
    # Journal digest includes the event stream: any fill, cost, timestamp or rejection alteration changes it.
    serialized = {"trades": [x.model_dump(mode="json") for x in journal],
                  "events": [x.model_dump(mode="json") for x in ledger]}
    return ReplayReport(evidence_kind=evidence_kind, source_sha256=source_sha256,
                        configuration_sha256=_digest(costs.model_dump(mode="json")),
                        journal_sha256=_digest(serialized),
                        quote_stream_sha256=_digest([b.model_dump(mode="json") for b in bars]),
                        qualification_eligible=False,
                        trades=tuple(journal), ledger_events=tuple(ledger), final_equity_usd=equity,
                        peak_equity_usd=peak, max_drawdown_fraction=drawdown,
                        net_pnl_usd=equity - costs.starting_equity_usd)
