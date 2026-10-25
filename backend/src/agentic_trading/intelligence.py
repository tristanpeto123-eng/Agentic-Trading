"""Sprint 4 research-only Scout A -> Strategist -> Scout B -> Guardian.

Deterministic, auditable reference policies, NOT trained neural networks. Scout B's
conditional historical net-R estimate is a deliberately simple, frozen baseline;
Sprint 6 owns learned models and Sprint 7 owns independent qualification.
No API, order routing, credentials, or approval mutation is exposed here.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from enum import StrEnum
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID, uuid5, NAMESPACE_URL

from pydantic import Field, field_validator, model_validator

from agentic_trading.contracts.common import EvidenceKind, FrozenModel, Sha256, require_utc
from agentic_trading.contracts.trading import (
    Decision, Direction, GuardianDecision, TradeAssessment, TradeProposal,
)
from agentic_trading.policy import guardian_allows
from agentic_trading.simulator import HistoricalOrder, ReplayCosts, ReplayReport, QuoteBar, replay

STEP = timedelta(minutes=15)
ZERO = Decimal('0')
ONE = Decimal('1')


def fingerprint(value: object) -> str:
    """Canonical JSON digest: deterministic across processes and Python hash seeds."""
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


class IntelligenceError(ValueError):
    """Refuse unsafe, unverifiable or future-dependent research decisions."""


class MarketState(StrEnum):
    TREND_UP = 'TREND_UP'
    TREND_DOWN = 'TREND_DOWN'
    RANGE = 'RANGE'
    CHOP = 'CHOP'
    UNCERTAIN = 'UNCERTAIN'


class VolatilityState(StrEnum):
    COMPRESSED = 'COMPRESSED'
    NORMAL = 'NORMAL'
    HIGH = 'HIGH'
    EXTREME = 'EXTREME'


class SignalCandle(FrozenModel):
    open_time: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)

    @field_validator('open_time')
    @classmethod
    def quarter_hour(cls, value: datetime) -> datetime:
        require_utc(value)
        if value.minute % 15 or value.second or value.microsecond:
            raise ValueError('M15 candle must start on a whole UTC quarter hour')
        return value

    @model_validator(mode='after')
    def coherent_ohlc(self):
        if self.high < max(self.open, self.low, self.close) or self.low > min(self.open, self.high, self.close):
            raise ValueError('Inconsistent M15 OHLC')
        return self

    @property
    def available_at(self) -> datetime:
        return self.open_time + STEP


class MarketWindow(FrozenModel):
    """Closed M15 observations only; never backfill holes or infer data rights."""
    instrument: Literal['XAUUSD'] = 'XAUUSD'
    source_sha256: Sha256
    evidence_kind: Literal[EvidenceKind.SYNTHETIC, EvidenceKind.HISTORICAL_UNVERIFIED, EvidenceKind.HISTORICAL_VERIFIED]
    price_basis: Literal['bid', 'ask', 'mid']
    as_of: datetime
    candles: tuple[SignalCandle, ...] = Field(min_length=1, max_length=1000)

    @field_validator('as_of')
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode='after')
    def closed_and_ordered(self):
        if self.candles[-1].available_at != self.as_of:
            raise ValueError('Window as_of must equal final closed candle availability')
        if any(b.open_time - a.open_time != STEP for a, b in zip(self.candles, self.candles[1:])):
            raise ValueError('M15 history requires contiguous, strictly ordered bars; gaps fail closed')
        return self


class ScoutAConfig(FrozenModel):
    lookback: int = Field(default=20, ge=14, le=64)
    min_history: int = Field(default=80, ge=48, le=256)
    trend_efficiency: Decimal = Field(default=Decimal('0.55'), gt=0, lt=1)
    range_efficiency: Decimal = Field(default=Decimal('0.20'), ge=0, lt=1)
    high_volatility_atr_pct: Decimal = Field(default=Decimal('0.004'), gt=0)
    extreme_volatility_atr_pct: Decimal = Field(default=Decimal('0.012'), gt=0)
    compressed_atr_pct: Decimal = Field(default=Decimal('0.00035'), gt=0)

    @model_validator(mode='after')
    def sensible(self):
        if self.trend_efficiency <= self.range_efficiency:
            raise ValueError('trend efficiency must exceed range efficiency')
        if not (self.compressed_atr_pct < self.high_volatility_atr_pct < self.extreme_volatility_atr_pct):
            raise ValueError('volatility thresholds must increase')
        if self.min_history <= self.lookback + 1:
            raise ValueError('min_history must exceed lookback')
        return self


class RegimeReport(FrozenModel):
    schema_version: Literal['scout_a_regime.v1'] = 'scout_a_regime.v1'
    market: MarketState
    volatility: VolatilityState
    confidence: Decimal = Field(ge=0, le=1)
    efficiency: Decimal = Field(ge=0, le=1)
    atr: Decimal = Field(ge=0)
    atr_pct: Decimal = Field(ge=0)
    h1_direction: Literal['UP', 'DOWN', 'FLAT', 'UNKNOWN']
    h4_direction: Literal['UP', 'DOWN', 'FLAT', 'UNKNOWN']
    reasons: tuple[str, ...]
    available_at: datetime
    input_sha256: Sha256
    policy_sha256: Sha256
    engine_kind: Literal['DETERMINISTIC_BASELINE'] = 'DETERMINISTIC_BASELINE'


def _completed_period_closes(window: MarketWindow, hours: int) -> tuple[Decimal, ...]:
    step = int(hours * 60 / 15)
    groups: dict[datetime, list[SignalCandle]] = {}
    for bar in window.candles:
        group_start = bar.open_time.replace(hour=(bar.open_time.hour // hours) * hours, minute=0)
        groups.setdefault(group_start, []).append(bar)
    return tuple(v[-1].close for v in groups.values() if len(v) == step
                 and v[0].open_time == v[-1].open_time.replace(hour=(v[-1].open_time.hour // hours) * hours, minute=0)
                 and v[-1].available_at.hour % hours == 0 and v[-1].available_at.minute == 0)


def _direction(points: tuple[Decimal, ...]) -> Literal['UP', 'DOWN', 'FLAT', 'UNKNOWN']:
    if len(points) < 2:
        return 'UNKNOWN'
    return 'UP' if points[-1] > points[-2] else 'DOWN' if points[-1] < points[-2] else 'FLAT'


def scout_a(window: MarketWindow, config: ScoutAConfig | None = None) -> RegimeReport:
    cfg = config or ScoutAConfig()
    history = window.candles
    input_sha = fingerprint([c.model_dump(mode='json') for c in history])
    cfg_sha = fingerprint(cfg.model_dump(mode='json'))
    h1 = _direction(_completed_period_closes(window, 1))
    h4 = _direction(_completed_period_closes(window, 4))
    if len(history) < cfg.min_history:
        return RegimeReport(market=MarketState.UNCERTAIN, volatility=VolatilityState.NORMAL,
                            confidence=ZERO, efficiency=ZERO, atr=ZERO, atr_pct=ZERO,
                            h1_direction=h1, h4_direction=h4, reasons=('INSUFFICIENT_HISTORY',),
                            available_at=window.as_of, input_sha256=input_sha, policy_sha256=cfg_sha)
    lookback = history[-(cfg.lookback + 1):]
    true_ranges = [max(bar.high - bar.low, abs(bar.high - prev.close), abs(bar.low - prev.close))
                   for prev, bar in zip(lookback, lookback[1:])]
    atr = sum(true_ranges, ZERO) / Decimal(len(true_ranges))
    atr_pct = atr / lookback[-1].close
    path = sum((abs(bar.close - prev.close) for prev, bar in zip(lookback, lookback[1:])), ZERO)
    efficiency = abs(lookback[-1].close - lookback[0].close) / path if path else ZERO
    volatility = (VolatilityState.EXTREME if atr_pct >= cfg.extreme_volatility_atr_pct else
                  VolatilityState.HIGH if atr_pct >= cfg.high_volatility_atr_pct else
                  VolatilityState.COMPRESSED if atr_pct <= cfg.compressed_atr_pct else VolatilityState.NORMAL)
    reasons: list[str] = []
    if h1 == 'UNKNOWN' or h4 == 'UNKNOWN':
        market = MarketState.UNCERTAIN
        reasons.append('INSUFFICIENT_COMPLETED_HIGHER_TIMEFRAME')
    elif h1 in ('UP', 'DOWN') and h4 in ('UP', 'DOWN') and h1 != h4:
        market = MarketState.UNCERTAIN
        reasons.append('H1_H4_CONFLICT')
    elif volatility == VolatilityState.EXTREME:
        market = MarketState.UNCERTAIN
        reasons.append('EXTREME_VOLATILITY')
    elif efficiency >= cfg.trend_efficiency and h1 == h4 and h1 in ('UP', 'DOWN'):
        direction = 'UP' if lookback[-1].close > lookback[0].close else 'DOWN'
        market = MarketState[f'TREND_{direction}'] if h1 == direction else MarketState.UNCERTAIN
        if market == MarketState.UNCERTAIN:
            reasons.append('H1_H4_MISMATCH_SIGNAL')
    elif efficiency <= cfg.range_efficiency:
        market = MarketState.RANGE
        reasons.append('LOW_DIRECTIONAL_EFFICIENCY')
    else:
        market = MarketState.CHOP
        reasons.append('CHOP_OR_UNCLEAR_TRANSITION')
    if volatility in (VolatilityState.HIGH, VolatilityState.COMPRESSED):
        reasons.append('NON_NORMAL_VOLATILITY')
    conf = min(ONE, efficiency) if market in (MarketState.TREND_UP, MarketState.TREND_DOWN) else (
        ONE - efficiency if market == MarketState.RANGE else ZERO)
    if market == MarketState.UNCERTAIN:
        conf = ZERO
    return RegimeReport(market=market, volatility=volatility, confidence=conf,
                        efficiency=efficiency, atr=atr, atr_pct=atr_pct,
                        h1_direction=h1, h4_direction=h4, reasons=tuple(reasons),
                        available_at=window.as_of, input_sha256=input_sha, policy_sha256=cfg_sha)


class StrategyConfig(FrozenModel):
    strategy_version: str = Field(default='strategist_b.baseline.v1', min_length=1)
    stop_atr_multiple: Decimal = Field(default=Decimal('1.5'), gt=0)
    target_atr_multiple: Decimal = Field(default=Decimal('3'), gt=0)
    range_edge_fraction: Decimal = Field(default=Decimal('0.20'), gt=0, lt=Decimal('0.5'))
    min_expected_net_r: Decimal = Field(default=Decimal('0.10'), ge=0)
    max_signal_age_minutes: int = Field(default=15, ge=1, le=60)


def proposal_digest(proposal: TradeProposal) -> str:
    return fingerprint({k: str(v) for k, v in proposal.model_dump(exclude={'schema_version', 'content_sha256'}).items()})


def propose_candidate(window: MarketWindow, regime: RegimeReport, *, student_id: UUID,
                      cfg: StrategyConfig | None = None) -> TradeProposal | None:
    """Rules-only candidate; caller must let Scout B score BEFORE final selection."""
    settings = cfg or StrategyConfig()
    if regime.available_at != window.as_of or regime.input_sha256 != fingerprint([
        c.model_dump(mode='json') for c in window.candles]):
        raise IntelligenceError('Regime and input window do not match')
    if regime.market in (MarketState.UNCERTAIN, MarketState.CHOP) or regime.volatility in (
            VolatilityState.EXTREME, VolatilityState.HIGH, VolatilityState.COMPRESSED):
        return None
    if regime.atr <= ZERO:
        return None
    last = window.candles[-1]
    ref = last.close
    side: Direction
    tactic: str
    if regime.market in (MarketState.TREND_UP, MarketState.TREND_DOWN):
        side = Direction.LONG if regime.market == MarketState.TREND_UP else Direction.SHORT
        if (side == Direction.LONG and last.close <= last.open) or (side == Direction.SHORT and last.close >= last.open):
            return None
        previous = window.candles[-21:-1]
        is_breakout = (last.close > max(c.high for c in previous) if side == Direction.LONG
                       else last.close < min(c.low for c in previous))
        tactic = 'BREAKOUT' if is_breakout else 'TREND_CONTINUATION'
    else:
        recent = window.candles[-21:-1]
        hi, lo = max(c.high for c in recent), min(c.low for c in recent)
        width = hi - lo
        if width <= ZERO:
            return None
        if ref <= lo + width * settings.range_edge_fraction and last.close >= last.open:
            side = Direction.LONG
        elif ref >= hi - width * settings.range_edge_fraction and last.close <= last.open:
            side = Direction.SHORT
        else:
            return None
        tactic = 'RANGE_REVERSION'
    stop_offset = regime.atr * settings.stop_atr_multiple
    target_offset = regime.atr * settings.target_atr_multiple
    stop = ref - stop_offset if side == Direction.LONG else ref + stop_offset
    target = ref + target_offset if side == Direction.LONG else ref - target_offset
    if stop <= ZERO or target <= ZERO:
        return None
    model_sha = fingerprint({'strategy': settings.model_dump(mode='json'),
                             'scout_a_policy_sha256': regime.policy_sha256})
    identity = '|'.join((str(student_id), str(window.as_of), window.source_sha256, tactic, model_sha))
    payload = dict(proposal_id=uuid5(NAMESPACE_URL, identity), revision=1, student_id=student_id,
                   strategy_version=settings.strategy_version, model_sha256=model_sha, instrument=window.instrument,
                   direction=side, entry_reference=ref, stop_price=stop, target_price=target,
                   tactic_id=tactic, thesis=f'{regime.market.value} / {tactic}; completed M15 only',
                   invalidation=f'Close breaches {stop}', observed_data_available_at=last.available_at,
                   created_at=window.as_of, expires_at=window.as_of + timedelta(minutes=settings.max_signal_age_minutes))
    payload['content_sha256'] = fingerprint({k: str(v) for k, v in payload.items()})
    return TradeProposal(**payload)


class OutcomeSample(FrozenModel):
    sample_id: UUID
    tactic_id: str = Field(min_length=1)
    market: MarketState
    net_r: Decimal
    closed_at: datetime
    source_sha256: Sha256
    evidence_kind: EvidenceKind

    @field_validator('closed_at')
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class ScoutBModel(FrozenModel):
    schema_version: Literal['scout_b_empirical.v1'] = 'scout_b_empirical.v1'
    trained_through: datetime
    samples: tuple[OutcomeSample, ...] = Field(min_length=1)
    min_bucket_samples: int = Field(default=12, ge=3, le=1000)

    @field_validator('trained_through')
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode='after')
    def only_mature_unique_closed_trades(self):
        if len({x.sample_id for x in self.samples}) != len(self.samples):
            raise ValueError('Duplicate closed-trade memory samples')
        if any(x.closed_at > self.trained_through for x in self.samples):
            raise ValueError('Scout B cannot train on future or open trades')
        if any(not x.net_r.is_finite() for x in self.samples):
            raise ValueError('Scout B net R must be finite')
        return self

    @property
    def sha256(self) -> str:
        return fingerprint(self.model_dump(mode='json'))


def scout_b(proposal: TradeProposal, regime: RegimeReport, window: MarketWindow,
            model: ScoutBModel) -> TradeAssessment | None:
    """Point-in-time empirical baseline, not a calibrated neural expected-return model."""
    if model.trained_through >= window.candles[0].open_time:
        raise IntelligenceError('Scout B training cutoff overlaps the evaluation window')
    if proposal.observed_data_available_at > window.as_of or regime.available_at != window.as_of:
        raise IntelligenceError('Scout B would use future observations')
    if proposal_digest(proposal) != proposal.content_sha256:
        raise IntelligenceError('Scout B proposal content hash mismatch')
    if any(s.source_sha256 == window.source_sha256 for s in model.samples):
        raise IntelligenceError('Scout B training/evaluation source overlap; independently split artifacts first')
    if proposal.created_at != window.as_of:
        raise IntelligenceError('Stale or mismatched proposal')
    matching = [x.net_r for x in model.samples if x.tactic_id == proposal.tactic_id
                and x.market == regime.market and x.evidence_kind == window.evidence_kind]
    if len(matching) < model.min_bucket_samples:
        return None
    expected = sum(matching, ZERO) / Decimal(len(matching))
    return TradeAssessment(proposal_id=proposal.proposal_id, proposal_revision=proposal.revision,
                           proposal_sha256=proposal.content_sha256, scout_b_model_sha256=model.sha256,
                           expected_net_r=expected, assessed_at=window.as_of)


class GuardianPolicy(FrozenModel):
    min_expected_net_r: Decimal = Field(default=Decimal('0.10'), ge=0)
    min_regime_confidence: Decimal = Field(default=Decimal('0.55'), ge=0, le=1)
    max_loss_fraction: Decimal = Field(default=Decimal('0.01'), gt=0, le=Decimal('0.05'))
    max_position_oz: Decimal = Field(default=Decimal('10'), gt=0)
    max_leverage: Decimal = Field(default=Decimal('2'), gt=0, le=20)
    max_spread_usd_per_oz: Decimal = Field(default=Decimal('0.5'), gt=0)
    commission_usd_per_oz_per_side: Decimal = Field(default=Decimal('0.05'), ge=0)
    slippage_usd_per_oz_per_side: Decimal = Field(default=Decimal('0.1'), ge=0)
    equity_usd: Decimal = Field(default=Decimal('1000'), gt=0)


class GuardianReview(FrozenModel):
    decision: GuardianDecision
    quantity_oz: Decimal = Field(ge=0)
    policy_sha256: Sha256


def guardian_a(proposal: TradeProposal, assessment: TradeAssessment, regime: RegimeReport,
               window: MarketWindow, policy: GuardianPolicy | None = None) -> GuardianReview:
    cfg = policy or GuardianPolicy()
    reasons: list[str] = []
    if proposal_digest(proposal) != proposal.content_sha256:
        reasons.append('PROPOSAL_CONTENT_HASH_INVALID')
    if assessment.proposal_id != proposal.proposal_id or assessment.proposal_revision != proposal.revision or (
            assessment.proposal_sha256 != proposal.content_sha256):
        reasons.append('ASSESSMENT_PROPOSAL_MISMATCH')
    if not (proposal.created_at <= assessment.assessed_at <= window.as_of < proposal.expires_at):
        reasons.append('ASSESSMENT_TIME_INVALID')
    if regime.available_at != window.as_of or proposal.observed_data_available_at > window.as_of:
        reasons.append('MARKET_TIME_INVALID')
    if regime.market not in (MarketState.TREND_UP, MarketState.TREND_DOWN, MarketState.RANGE):
        reasons.append('UNSUITABLE_REGIME')
    if regime.volatility != VolatilityState.NORMAL:
        reasons.append('UNSUITABLE_VOLATILITY')
    if regime.confidence < cfg.min_regime_confidence:
        reasons.append('LOW_REGIME_CONFIDENCE')
    if assessment.expected_net_r < cfg.min_expected_net_r:
        reasons.append('INSUFFICIENT_EXPECTED_NET_R')
    if proposal.instrument != 'XAUUSD':
        reasons.append('UNSUPPORTED_MARKET')
    size = ZERO
    # Conservative estimate accounts for possible adverse entry slippage, stop slippage and both commissions.
    distance = abs(proposal.entry_reference - proposal.stop_price)
    loss_per_oz = distance + 2 * cfg.slippage_usd_per_oz_per_side + 2 * cfg.commission_usd_per_oz_per_side
    if distance <= ZERO or loss_per_oz <= ZERO:
        reasons.append('INVALID_STOP_DISTANCE')
    else:
        loss_budget = cfg.equity_usd * cfg.max_loss_fraction
        risk_size = loss_budget / loss_per_oz
        leverage_size = cfg.equity_usd * cfg.max_leverage / (proposal.entry_reference + cfg.slippage_usd_per_oz_per_side)
        size = min(risk_size, leverage_size, cfg.max_position_oz)
        size = size.quantize(Decimal('0.0001'), rounding=ROUND_DOWN) if size >= Decimal('0.0001') else ZERO
        if size <= ZERO:
            reasons.append('NO_SAFE_POSITION_SIZE')
    decision = GuardianDecision(proposal_id=proposal.proposal_id, proposal_revision=proposal.revision,
                                proposal_sha256=proposal.content_sha256,
                                decision=Decision.DENIED if reasons else Decision.APPROVED,
                                reasons=tuple(reasons or ['WITHIN_RESEARCH_RISK_LIMITS']), decided_at=window.as_of)
    return GuardianReview(decision=decision, quantity_oz=size if not reasons else ZERO,
                          policy_sha256=fingerprint(cfg.model_dump(mode='json')))


class ThesisObservation(FrozenModel):
    schema_version: Literal['guardian_thesis_observation.v1'] = 'guardian_thesis_observation.v1'
    status: Literal['VALID', 'WEAKENING', 'INVALIDATED', 'UNCERTAIN']
    observed_at: datetime
    reason: str
    action_authorised: Literal[False] = False


def observe_thesis(proposal: TradeProposal, window: MarketWindow) -> ThesisObservation:
    """Guardian A thesis observation only; cannot modify positions or orders."""
    if window.as_of < proposal.observed_data_available_at:
        raise IntelligenceError('Cannot monitor a trade using a future window')
    if window.instrument != proposal.instrument:
        return ThesisObservation(status='UNCERTAIN', observed_at=window.as_of, reason='INSTRUMENT_MISMATCH')
    close = window.candles[-1].close
    if (proposal.direction == Direction.LONG and close <= proposal.stop_price) or (
            proposal.direction == Direction.SHORT and close >= proposal.stop_price):
        status, reason = 'INVALIDATED', 'CLOSE_BREACHED_STOP_THESIS'
    elif (proposal.direction == Direction.LONG and close < proposal.entry_reference) or (
            proposal.direction == Direction.SHORT and close > proposal.entry_reference):
        status, reason = 'WEAKENING', 'PRICE_AGAINST_ENTRY_THESIS'
    else:
        status, reason = 'VALID', 'NO_INVALIDATION_OBSERVED'
    return ThesisObservation(status=status, observed_at=window.as_of, reason=reason)


class DecisionTrace(FrozenModel):
    schema_version: Literal['historical_intelligence.v1'] = 'historical_intelligence.v1'
    source_sha256: Sha256
    evidence_kind: EvidenceKind
    student_id: UUID
    observed_at: datetime
    regime: RegimeReport
    candidate: TradeProposal | None
    assessment: TradeAssessment | None
    guardian: GuardianReview | None
    selected: bool
    reason: str
    trace_sha256: Sha256
    research_only: Literal[True] = True
    qualification_eligible: Literal[False] = False


def research_decision(window: MarketWindow, student_id: UUID, model: ScoutBModel | None,
                      *, scout_config: ScoutAConfig | None = None,
                      strategy_config: StrategyConfig | None = None,
                      guardian_policy: GuardianPolicy | None = None) -> DecisionTrace:
    """Scout A -> Strategist candidate -> Scout B -> Strategist select -> Guardian.

    Neither selection nor guardian approval grants paper/live privileges. Research only.
    """
    regime = scout_a(window, scout_config)
    cfg = strategy_config or StrategyConfig()
    candidate = propose_candidate(window, regime, student_id=student_id, cfg=cfg)
    assessment: TradeAssessment | None = None
    guardian: GuardianReview | None = None
    if candidate is None:
        reason = 'STRATEGIST_ABSTAINED'
    elif model is None:
        reason = 'SCOUT_B_UNTRAINED'
    else:
        assessment = scout_b(candidate, regime, window, model)
        if assessment is None:
            reason = 'SCOUT_B_INSUFFICIENT_CLOSED_OUTCOMES'
        elif assessment.expected_net_r < cfg.min_expected_net_r:
            reason = 'STRATEGIST_REJECTED_NEGATIVE_EXPECTANCY'
        else:
            guardian = guardian_a(candidate, assessment, regime, window, guardian_policy)
            reason = ('RESEARCH_INTENT_APPROVED' if guardian.decision.decision == Decision.APPROVED
                      else 'GUARDIAN_VETO')
    selected = reason == 'RESEARCH_INTENT_APPROVED'
    raw = dict(source_sha256=window.source_sha256, evidence_kind=window.evidence_kind.value,
               student_id=str(student_id), observed_at=window.as_of.isoformat(),
               regime=regime.model_dump(mode='json'),
               candidate=candidate.model_dump(mode='json') if candidate else None,
               assessment=assessment.model_dump(mode='json') if assessment else None,
               guardian=guardian.model_dump(mode='json') if guardian else None,
               selected=selected, reason=reason)
    return DecisionTrace(source_sha256=window.source_sha256, evidence_kind=window.evidence_kind,
                         student_id=student_id, observed_at=window.as_of,
                         regime=regime, candidate=candidate, assessment=assessment,
                         guardian=guardian, selected=selected, reason=reason,
                         trace_sha256=fingerprint(raw))


def trace_digest(trace: DecisionTrace) -> str:
    return fingerprint(dict(source_sha256=trace.source_sha256, evidence_kind=trace.evidence_kind.value,
                            student_id=str(trace.student_id), observed_at=trace.observed_at.isoformat(),
                            regime=trace.regime.model_dump(mode='json'),
                            candidate=trace.candidate.model_dump(mode='json') if trace.candidate else None,
                            assessment=trace.assessment.model_dump(mode='json') if trace.assessment else None,
                            guardian=trace.guardian.model_dump(mode='json') if trace.guardian else None,
                            selected=trace.selected, reason=trace.reason))


def historical_research_replay(trace: DecisionTrace, window: MarketWindow,
                               bars: tuple[QuoteBar, ...], costs: ReplayCosts,
                               as_of: datetime, execution_source_sha256: Sha256) -> ReplayReport:
    """Optional S3 integration; never creates or routes broker orders."""
    if not trace.selected or not trace.candidate or not trace.assessment or not trace.guardian:
        raise IntelligenceError('No Guardian-approved historical research intent')
    if execution_source_sha256 == window.source_sha256:
        raise IntelligenceError('Signal and M1 execution archives require separately identifiable source artifacts')
    if trace.trace_sha256 != trace_digest(trace):
        raise IntelligenceError('Historical decision trace was modified after decision')
    if trace.observed_at != window.as_of or trace.source_sha256 != window.source_sha256 or (
            trace.regime.input_sha256 != fingerprint([c.model_dump(mode='json') for c in window.candles])):
        raise IntelligenceError('Trace is not bound to this immutable signal window')
    if trace.candidate.observed_data_available_at > trace.observed_at:
        raise IntelligenceError('Future signal')
    if trace.candidate.content_sha256 != proposal_digest(trace.candidate):
        raise IntelligenceError('Proposal was modified after Scout B assessment')
    if not bars or bars[0].open_time <= trace.observed_at:
        raise IntelligenceError('Execution M1 tape must start after completed signal and decision')
    if not guardian_allows(trace.candidate, trace.assessment, trace.guardian.decision):
        raise IntelligenceError('Guardian decision and assessment failed binding')
    order = HistoricalOrder(proposal=trace.candidate, assessment=trace.assessment,
                            guardian=trace.guardian.decision, quantity_oz=trace.guardian.quantity_oz)
    return replay(bars=bars, orders=(order,), costs=costs,
                  evidence_kind=trace.evidence_kind, source_sha256=execution_source_sha256, as_of=as_of)
