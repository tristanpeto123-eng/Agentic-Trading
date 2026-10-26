"""Sprint 3: historical execution scenarios use SYNTHETIC FIXTURES ONLY."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentic_trading.contracts.common import EvidenceKind
from agentic_trading.contracts.trading import TradeProposal, TradeAssessment, GuardianDecision
from agentic_trading.simulator import QuoteBar, ReplayCosts, HistoricalOrder, ReplayError, replay

T = datetime(2025, 4, 7, 10, 0, tzinfo=timezone.utc)
HASH = 'a' * 64


def quote(i=0, bid=(100, 101, 99, 100), ask=(100.2, 101.2, 99.2, 100.2)):
    vals = dict(zip(('open', 'high', 'low', 'close'), bid))
    vals.update({f'ask_{k}': v for k, v in zip(('open', 'high', 'low', 'close'), ask)})
    vals.update({f'bid_{k}': vals.pop(k) for k in ('open', 'high', 'low', 'close')})
    return QuoteBar(open_time=T+timedelta(minutes=i), **vals)


def conf(**changes):
    d = dict(commission_usd_per_oz_per_side='0.05',slippage_usd_per_oz_per_side='0.1',
             max_spread_usd_per_oz='0.5',starting_equity_usd='1000',max_position_oz='10',
             max_risk_fraction='0.05',max_leverage='2',max_holding_minutes=10)
    d.update(changes)
    return ReplayCosts(**d)


def guarded(*, direction='LONG', stop='98', target='102', modified=False, decided_seconds=3):
    p = TradeProposal(
        proposal_id=uuid4(), revision=1, student_id=uuid4(), strategy_version='fixture.1',
        model_sha256=HASH, instrument='XAUUSD', direction=direction,
        entry_reference='100' if direction=='LONG' else '100.2', stop_price=stop, target_price=target,
        tactic_id='fixture', thesis='Synthetic replay only', invalidation='Fixture stopped',
        observed_data_available_at=T, created_at=T, expires_at=T+timedelta(minutes=10),
        content_sha256='b'*64)
    a = TradeAssessment(proposal_id=p.proposal_id, proposal_revision=1,
                        proposal_sha256=p.content_sha256, scout_b_model_sha256=HASH,
                        expected_net_r='1.0', assessed_at=T+timedelta(seconds=2))
    g = GuardianDecision(proposal_id=p.proposal_id, proposal_revision=1,proposal_sha256=p.content_sha256,
                         decision='DENIED' if modified else 'APPROVED', reasons=('fixture',),
                         decided_at=T+timedelta(seconds=decided_seconds))
    return HistoricalOrder(proposal=p, assessment=a, guardian=g, quantity_oz='2')


def play(bars, orders=None, *, costs=None, kind=EvidenceKind.SYNTHETIC, as_of=None):
    return replay(bars=tuple(bars), orders=tuple(orders or (guarded(),)), costs=costs or conf(),
                  evidence_kind=kind, source_sha256=HASH,
                  as_of=as_of or (bars[-1].open_time+timedelta(minutes=1)))


def test_long_fill_costs_spread_once_and_deterministic_hash():
    bars=[quote(0),quote(1, bid=(100,103,99.5,102), ask=(100.2,103.2,99.7,102.2))]
    o=guarded()
    a=play(bars,[o]); b=play(bars,[o])
    t=a.trades[0]
    assert a.journal_sha256 == b.journal_sha256 and a.configuration_sha256==b.configuration_sha256
    assert t.status=='CLOSED' and t.exit_reason=='TARGET'
    assert t.entry_at == T+timedelta(minutes=1)  # Decision at T+3 seconds cannot fill T open.
    assert t.entry_fill == Decimal('100.3')
    assert t.exit_fill == Decimal('101.9')
    assert t.gross_pnl_usd == Decimal('3.2')
    assert t.commissions_usd == Decimal('0.20')
    assert t.net_pnl_usd == Decimal('3.00')
    assert a.final_equity_usd==Decimal('1003.00') and not a.qualification_eligible
    assert [e.event_type for e in a.ledger_events] == ['ENTRY', 'EXIT']
    assert sum(e.commission_usd for e in a.ledger_events) == t.commissions_usd
    assert a.quote_stream_sha256 == b.quote_stream_sha256


def test_stop_first_if_both_target_and_stop_hit():
    bars=[quote(0),quote(1,bid=(100,103,97,101),ask=(100.2,103.2,97.2,101.2))]
    t=play(bars).trades[0]
    assert t.status=='CLOSED' and t.ambiguity and t.exit_reason=='STOP_PRIORITY_AMBIGUOUS'
    assert t.exit_fill==Decimal('97.9') and t.net_pnl_usd < 0


def test_short_bid_entry_ask_exit_and_gap_through_stop():
    order=guarded(direction='SHORT',stop='102',target='98')
    bars=[quote(0),quote(1,bid=(100,100.5,99,99.5),ask=(100.2,100.7,99.2,99.7)),
          quote(2,bid=(105,106,104,105),ask=(105.2,106.2,104.2,105.2))]
    t=play(bars,[order]).trades[0]
    assert t.status=='CLOSED' and t.exit_reason=='STOP'
    assert t.entry_fill==Decimal('99.9') and t.exit_fill==Decimal('105.3')
    assert t.net_pnl_usd < Decimal('-10')  # Worse-than-stop gap allowed.


def test_different_fixture_short_hits_target():
    order=guarded(direction='SHORT',stop='102',target='98')
    bars=[quote(0),quote(1,bid=(100,100.5,98.5,99.5),ask=(100.2,100.7,98.7,99.7)),
          quote(2,bid=(99,99.5,97,97.5),ask=(99.2,99.7,97.2,97.7))]
    t=play(bars,[order]).trades[0]
    assert t.status=='CLOSED' and t.exit_reason=='TARGET' and t.net_pnl_usd>0


def test_gap_while_exposed_becomes_unresolved_not_profitable():
    bars=[quote(0),quote(1,bid=(100,100.5,99.5,100),ask=(100.2,100.7,99.7,100.2)),
          quote(3,bid=(100,105,99,104),ask=(100.2,105.2,99.2,104.2))]
    t=play(bars).trades[0]
    assert t.status=='UNRESOLVED' and t.reason=='MISSING_M1_DURING_POSITION'
    assert t.net_pnl_usd is None and not play(bars).qualification_eligible


def test_end_of_tape_open_is_not_closed_or_labeled_good():
    bars=[quote(0),quote(1,bid=(100,100.5,99.5,100),ask=(100.2,100.7,99.7,100.2))]
    t=play(bars).trades[0]
    assert t.status=='UNRESOLVED' and t.reason=='END_OF_TAPE_OPEN_POSITION'


def test_spread_risk_leverage_and_guardian_denials():
    base=[quote(0),quote(1)]
    assert play(base,[guarded(modified=True)]).trades[0].reason=='GUARDIAN_OR_SCOUT_B_NOT_VALID'
    assert play(base,[guarded()],costs=conf(max_spread_usd_per_oz='0.1')).trades[0].reason=='SPREAD_LIMIT'
    assert play(base,[guarded()],costs=conf(max_leverage='0.1')).trades[0].reason=='LEVERAGE_LIMIT'
    assert play(base,[guarded()],costs=conf(max_risk_fraction='0.001')).trades[0].reason=='RISK_LIMIT'
    assert play(base,[guarded()],costs=conf(max_position_oz='1')).trades[0].reason=='MAX_POSITION_SIZE'


def test_future_candle_and_unsorted_bars_rejected():
    bars=[quote(0),quote(1)]
    with pytest.raises(ReplayError,match='unfinished or future'):
        play(bars,as_of=T+timedelta(minutes=1))
    with pytest.raises(ReplayError,match='chronological'):
        play(list(reversed(bars)))
    with pytest.raises(ValidationError):
        quote(0,bid=(100,99,98,100))
    with pytest.raises(ValidationError):
        quote(0,ask=(99.9,101,99,100))


def test_duplicate_orders_refused_and_other_instrument_rejected():
    bars=[quote(0),quote(1)]
    order=guarded()
    with pytest.raises(ReplayError, match='Duplicate proposal'):
        play(bars,[order,order])
    other=order.model_copy(update={'proposal':order.proposal.model_copy(update={'instrument':'EURUSD'})})
    assert play(bars,[other]).trades[0].reason=='UNSUPPORTED_INSTRUMENT'


def test_quarantined_and_claimed_verified_results_never_qualify_without_examiner():
    bars=[quote(0),quote(1,bid=(100,103,99.5,102),ask=(100.2,103.2,99.7,102.2))]
    assert not play(bars,kind=EvidenceKind.HISTORICAL_UNVERIFIED).qualification_eligible
    assert not play(bars,kind=EvidenceKind.HISTORICAL_VERIFIED).qualification_eligible


def test_proposal_revision_mismatch_rejected():
    bars=[quote(0),quote(1)]
    order=guarded()
    altered=order.model_copy(update={'proposal':order.proposal.model_copy(update={'revision':2})})
    assert play(bars,[altered]).trades[0].reason=='GUARDIAN_OR_SCOUT_B_NOT_VALID'


def test_risk_equity_never_mutates_on_rejected_intent():
    bars=[quote(0),quote(1)]
    a=play(bars,[guarded(modified=True)])
    assert a.net_pnl_usd==0 and a.final_equity_usd==1000


def test_long_stop_slips_on_gap_and_loss_can_exceed_one_r():
    bars=[quote(0),
          quote(1,bid=(100,100.5,99,100),ask=(100.2,100.7,99.2,100.2)),
          quote(2,bid=(95,96,94,95),ask=(95.2,96.2,94.2,95.2))]
    t=play(bars).trades[0]
    assert t.status=='CLOSED' and t.exit_reason=='STOP'
    assert t.exit_fill==Decimal('94.9') and t.net_r < -1


def test_trading_simulation_does_not_allow_overlapping_position():
    a=guarded()
    b=guarded(decided_seconds=4)
    bars=[quote(0),quote(1,bid=(100,100.5,99.5,100),ask=(100.2,100.7,99.7,100.2)),
          quote(2,bid=(100,103,99.5,102),ask=(100.2,103.2,99.7,102.2))]
    report=play(bars,[a,b])
    assert report.trades[0].status=='CLOSED'
    assert report.trades[1].reason=='OVERLAPPING_POSITION'
    assert [e.event_type for e in report.ledger_events] == ['ENTRY','EXIT','REJECTED']


def test_orders_require_monotonic_decision_time():
    a=guarded(decided_seconds=5)
    b=guarded(decided_seconds=3)
    with pytest.raises(ReplayError,match='sorted'):
        play([quote(0),quote(1)],[a,b])


def test_timeout_marks_settlement_on_closed_minute():
    bars=[quote(0),quote(1,bid=(100,100.5,99.5,100),ask=(100.2,100.7,99.7,100.2)),
          quote(2,bid=(100,100.5,99.5,100.4),ask=(100.2,100.7,99.7,100.6))]
    t=play(bars,costs=conf(max_holding_minutes=2)).trades[0]
    assert t.status=='CLOSED' and t.exit_reason=='TIMEOUT'
    assert t.exit_at==T+timedelta(minutes=3)
