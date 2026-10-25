"""Sprint 4 deterministic offline intelligence, SYNTHETIC FIXTURES ONLY."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentic_trading.contracts.common import EvidenceKind
from agentic_trading.contracts.trading import Decision
from agentic_trading.intelligence import (
    GuardianPolicy, IntelligenceError, MarketState, MarketWindow, OutcomeSample,
    ScoutAConfig, ScoutBModel, SignalCandle, StrategyConfig, VolatilityState,
    guardian_a, historical_research_replay, observe_thesis, propose_candidate,
    research_decision, scout_a, scout_b,
)
from agentic_trading.simulator import QuoteBar, ReplayCosts

START = datetime(2025, 4, 7, 0, tzinfo=timezone.utc)
STUDENT = uuid4()
SRC = 'a' * 64


def window(*, trend=Decimal('0.4'), count=96, kind=EvidenceKind.SYNTHETIC,
           close_start=Decimal('1800'), price_basis='mid'):
    bars = []
    for i in range(count):
        op = close_start + trend * i
        cl = op + trend
        bars.append(SignalCandle(open_time=START + timedelta(minutes=15*i),
                                 open=op, high=max(op, cl) + Decimal('0.5'),
                                 low=min(op, cl) - Decimal('0.5'), close=cl))
    return MarketWindow(source_sha256=SRC, evidence_kind=kind, price_basis=price_basis,
                        as_of=bars[-1].available_at, candles=tuple(bars))


def calibrator(w, tactic='TREND_CONTINUATION', regime=MarketState.TREND_UP, *, reward='0.35', n=15,
               kind=EvidenceKind.SYNTHETIC):
    samples = [OutcomeSample(sample_id=uuid4(), tactic_id=tactic, market=regime,
                             net_r=Decimal(reward), evidence_kind=kind, source_sha256='b'*64,
                             closed_at=START - timedelta(days=i+2)) for i in range(n)]
    return ScoutBModel(trained_through=START - timedelta(days=1), samples=tuple(samples))


def quote_bar(t, px=Decimal('1840'), spread=Decimal('0.2'), width=Decimal('0.6')):
    return QuoteBar(open_time=t, bid_open=px, bid_high=px + width, bid_low=px - width,
                    bid_close=px, ask_open=px+spread, ask_high=px+spread+width,
                    ask_low=px+spread-width, ask_close=px+spread)


def costs():
    return ReplayCosts(commission_usd_per_oz_per_side='0.05',
                       slippage_usd_per_oz_per_side='0.1', max_spread_usd_per_oz='0.5',
                       starting_equity_usd='1000', max_position_oz='10',
                       max_risk_fraction='0.05', max_leverage='2', max_holding_minutes=3)


def test_scout_a_confirmed_multitimeframe_trend_and_normal_volatility():
    w=window()
    r=scout_a(w)
    assert r.market == MarketState.TREND_UP
    assert r.volatility == VolatilityState.NORMAL
    assert r.h1_direction == r.h4_direction == 'UP'
    assert r.available_at == w.candles[-1].available_at
    assert r.efficiency == 1
    assert r.input_sha256 == scout_a(w).input_sha256
    assert r.engine_kind == 'DETERMINISTIC_BASELINE'


def test_downtrend_and_candidate_direction():
    w=window(trend=Decimal('-0.4'))
    r=scout_a(w)
    assert r.market == MarketState.TREND_DOWN
    p=propose_candidate(w,r,student_id=STUDENT)
    assert p and p.direction.value == 'SHORT' and p.stop_price > p.entry_reference > p.target_price


def test_scout_a_insufficient_history_abstains():
    w=window(count=24)
    r=scout_a(w)
    assert r.market == MarketState.UNCERTAIN
    assert 'INSUFFICIENT_HISTORY' in r.reasons
    assert propose_candidate(w,r,student_id=STUDENT) is None


def test_window_requires_closed_candles_no_gaps_and_utc():
    w=window()
    with pytest.raises(ValidationError, match='final closed candle'):
        MarketWindow(source_sha256=SRC, evidence_kind=EvidenceKind.SYNTHETIC,
                     price_basis='mid', candles=w.candles, as_of=w.as_of-timedelta(minutes=1))
    with pytest.raises(ValidationError, match='contiguous'):
        MarketWindow(source_sha256=SRC, evidence_kind=EvidenceKind.SYNTHETIC,
                     price_basis='mid', candles=w.candles[:20]+w.candles[21:], as_of=w.as_of)
    with pytest.raises(ValidationError, match='UTC'):
        SignalCandle(open_time=datetime(2025,4,7), open=1, high=2, low=1, close=1)
    with pytest.raises(ValidationError, match='Inconsistent'):
        SignalCandle(open_time=START, open=100, high=99, low=98, close=100)


def test_scout_b_point_in_time_with_only_mature_and_matching_closed_trades():
    w=window()
    r=scout_a(w)
    p=propose_candidate(w,r,student_id=STUDENT)
    assert p and p.tactic_id=='TREND_CONTINUATION'
    m=calibrator(w)
    a=scout_b(p,r,w,m)
    assert a and a.expected_net_r == Decimal('0.35')
    assert a.proposal_sha256 == p.content_sha256
    assert scout_b(p,r,w,calibrator(w,n=5)) is None
    assert scout_b(p,r,w,calibrator(w,kind=EvidenceKind.HISTORICAL_VERIFIED)) is None
    with pytest.raises(ValidationError, match='future or open'):
        ScoutBModel(trained_through=START-timedelta(days=3),samples=m.samples)
    with pytest.raises(IntelligenceError, match='overlaps'):
        scout_b(p,r,w,m.model_copy(update={'trained_through':w.candles[0].open_time}))
    with pytest.raises(ValidationError, match='Duplicate'):
        ScoutBModel(trained_through=m.trained_through, samples=(m.samples[0],m.samples[0]))


def test_full_decision_pipeline_is_deterministic_and_research_only():
    w=window()
    m=calibrator(w)
    a=research_decision(w,STUDENT,m)
    b=research_decision(w,STUDENT,m)
    assert a.selected and a.reason=='RESEARCH_INTENT_APPROVED'
    assert a.assessment and a.assessment.expected_net_r == Decimal('0.35')
    assert a.guardian and a.guardian.decision.decision == Decision.APPROVED
    assert a.candidate and a.candidate.content_sha256 == b.candidate.content_sha256
    assert a.trace_sha256 == b.trace_sha256
    assert a.qualification_eligible is False and a.research_only
    assert a.guardian.quantity_oz > 0


def test_untrained_and_insufficient_evidence_abstain():
    w=window()
    assert research_decision(w,STUDENT,None).reason=='SCOUT_B_UNTRAINED'
    assert research_decision(w,STUDENT,calibrator(w,n=3)).reason=='SCOUT_B_INSUFFICIENT_CLOSED_OUTCOMES'


def test_strategist_rejects_negative_expectancy_after_scout_b_scoring():
    w=window()
    a=research_decision(w,STUDENT,calibrator(w,reward='-0.8'))
    assert a.reason=='STRATEGIST_REJECTED_NEGATIVE_EXPECTANCY'
    assert not a.selected and a.guardian is None and a.assessment is not None


def test_guardian_vetoes_risk_and_preserves_nonexecution():
    w=window()
    m=calibrator(w)
    a=research_decision(w,STUDENT,m,guardian_policy=GuardianPolicy(min_expected_net_r=Decimal('0.5')))
    assert not a.selected and a.reason=='GUARDIAN_VETO'
    assert a.guardian and a.guardian.decision.decision == Decision.DENIED
    assert 'INSUFFICIENT_EXPECTED_NET_R' in a.guardian.decision.reasons
    assert a.guardian.quantity_oz == 0


def test_approved_guardian_is_bound_to_exact_proposal_revision():
    w=window()
    d=research_decision(w,STUDENT,calibrator(w))
    assert d.candidate and d.assessment and d.guardian
    changed=d.candidate.model_copy(update={'revision':2})
    denied=guardian_a(changed,d.assessment,d.regime,w)
    assert denied.decision.decision==Decision.DENIED
    assert 'ASSESSMENT_PROPOSAL_MISMATCH' in denied.decision.reasons


def test_thesis_monitor_does_not_authorise_interventions():
    w=window()
    p=research_decision(w,STUDENT,calibrator(w)).candidate
    assert p
    a=observe_thesis(p,w)
    assert a.status=='VALID' and not a.action_authorised
    changed=window(close_start=Decimal('1600'))
    assert observe_thesis(p,changed).status=='INVALIDATED'


def test_synthetic_trade_flows_to_s3_engine_and_stays_unqualified():
    w=window()
    d=research_decision(w,STUDENT,calibrator(w))
    assert d.candidate
    start = w.as_of + timedelta(minutes=1)
    px=d.candidate.entry_reference
    bars=(quote_bar(start,px), quote_bar(start+timedelta(minutes=1),px),
          quote_bar(start+timedelta(minutes=2),px))
    result=historical_research_replay(d,w,bars,costs(),as_of=start+timedelta(minutes=3),execution_source_sha256='c'*64)
    assert len(result.trades)==1
    assert not result.qualification_eligible and result.evidence_kind==EvidenceKind.SYNTHETIC
    assert result.journal_sha256 == historical_research_replay(d,w,bars,costs(),as_of=start+timedelta(minutes=3),execution_source_sha256='c'*64).journal_sha256


def test_replay_rejects_missing_approval_or_mismatched_source():
    w=window()
    d=research_decision(w,STUDENT,None)
    with pytest.raises(IntelligenceError,match='No Guardian-approved'):
        historical_research_replay(d,w,(quote_bar(w.as_of+timedelta(minutes=1)),),costs(),
                                   as_of=w.as_of+timedelta(minutes=2),execution_source_sha256='c'*64)
    approved=research_decision(w,STUDENT,calibrator(w))
    wrong=w.model_copy(update={'source_sha256':'d'*64})
    with pytest.raises(IntelligenceError,match='immutable signal window'):
        historical_research_replay(approved,wrong,(quote_bar(w.as_of+timedelta(minutes=1)),),costs(),
                                   as_of=w.as_of+timedelta(minutes=2),execution_source_sha256='c'*64)


def test_unsafe_volatility_abstains_without_proposals():
    w=window(trend=Decimal('20'))
    regime=scout_a(w)
    assert regime.volatility in (VolatilityState.HIGH,VolatilityState.EXTREME)
    assert not research_decision(w,STUDENT,calibrator(w)).selected


def test_scout_configuration_rejects_inverted_thresholds():
    with pytest.raises(ValidationError):
        ScoutAConfig(range_efficiency='0.7',trend_efficiency='0.5')


def test_breakout_tactic_is_different_from_trend_continuation():
    w=window(trend=Decimal('0.9'))
    r=scout_a(w)
    assert r.market==MarketState.TREND_UP
    p=propose_candidate(w,r,student_id=STUDENT)
    assert p and p.tactic_id=='BREAKOUT'


def test_range_strategy_requires_edge_and_confirming_candle():
    values=('1799.5','1802','1799.4','1799.6')
    candles=[]
    for i in range(96):
        cl=Decimal(values[i%4]); op=Decimal(values[(i-1)%4])
        candles.append(SignalCandle(open_time=START+timedelta(minutes=15*i),open=op,
                                    high=max(op,cl)+Decimal('0.5'),
                                    low=min(op,cl)-Decimal('0.5'),close=cl))
    w=MarketWindow(source_sha256=SRC,evidence_kind=EvidenceKind.SYNTHETIC,
                   price_basis='mid',as_of=candles[-1].available_at,candles=tuple(candles))
    r=scout_a(w)
    assert r.market==MarketState.RANGE
    p=propose_candidate(w,r,student_id=STUDENT)
    assert p and p.tactic_id=='RANGE_REVERSION' and p.direction.value=='LONG'


def test_training_and_eval_cannot_reuse_identical_frozen_source():
    w=window(); r=scout_a(w)
    p=propose_candidate(w,r,student_id=STUDENT)
    model=calibrator(w)
    polluted=model.model_copy(update={'samples':tuple(
        x.model_copy(update={'source_sha256':SRC}) for x in model.samples)})
    with pytest.raises(IntelligenceError,match='source overlap'):
        scout_b(p,r,w,polluted)


def test_mutated_proposal_hash_fails_scout_b_and_guardian():
    w=window(); d=research_decision(w,STUDENT,calibrator(w))
    assert d.candidate and d.assessment
    changed=d.candidate.model_copy(update={'target_price':d.candidate.target_price+Decimal('10')})
    with pytest.raises(IntelligenceError,match='content hash'):
        scout_b(changed,d.regime,w,calibrator(w))
    review=guardian_a(changed,d.assessment,d.regime,w)
    assert review.decision.decision==Decision.DENIED
    assert 'PROPOSAL_CONTENT_HASH_INVALID' in review.decision.reasons


def test_replay_rejects_trace_mutation_and_same_instant_m1():
    w=window(); d=research_decision(w,STUDENT,calibrator(w))
    manipulated=d.model_copy(update={'reason':'FAKE'})
    with pytest.raises(IntelligenceError,match='trace was modified'):
        historical_research_replay(manipulated,w,(quote_bar(w.as_of+timedelta(minutes=1)),),
                                   costs(),as_of=w.as_of+timedelta(minutes=2),execution_source_sha256='c'*64)
    with pytest.raises(IntelligenceError,match='start after'):
        historical_research_replay(d,w,(quote_bar(w.as_of),quote_bar(w.as_of+timedelta(minutes=1))),
                                   costs(),as_of=w.as_of+timedelta(minutes=2),execution_source_sha256='c'*64)


def test_no_learned_neural_models_or_qualifying_claims():
    w=window(); d=research_decision(w,STUDENT,calibrator(w))
    assert d.research_only and not d.qualification_eligible
    assert d.regime.engine_kind=='DETERMINISTIC_BASELINE'
    assert d.assessment.schema_version=='trade_assessment.v1'
    assert d.candidate.strategy_version=='strategist_b.baseline.v1'


def test_execution_tape_provenance_must_be_distinct_from_signal_source():
    w=window(); d=research_decision(w,STUDENT,calibrator(w))
    with pytest.raises(IntelligenceError,match='separately identifiable'):
        historical_research_replay(d,w,(quote_bar(w.as_of+timedelta(minutes=1)),),
                                   costs(),as_of=w.as_of+timedelta(minutes=2),
                                   execution_source_sha256=w.source_sha256)


def test_guardian_size_is_conservative_at_max_allowed_spread():
    w=window()
    d=research_decision(w,STUDENT,calibrator(w))
    assert d.selected and d.candidate and d.guardian
    p=d.candidate
    policy=GuardianPolicy()
    worst_entry=p.entry_reference+policy.max_spread_usd_per_oz+policy.slippage_usd_per_oz_per_side
    assert d.guardian.quantity_oz*worst_entry <= policy.equity_usd*policy.max_leverage
    loss_unit=(abs(p.entry_reference-p.stop_price)+policy.max_spread_usd_per_oz+
               2*policy.slippage_usd_per_oz_per_side+2*policy.commission_usd_per_oz_per_side)
    assert d.guardian.quantity_oz*loss_unit <= policy.equity_usd*policy.max_loss_fraction
