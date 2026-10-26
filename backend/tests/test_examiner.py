"""Sprint 7 acceptance: frozen exam comparisons never grant financial authority."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from agentic_trading.contracts.trading import TradeProposal, TradeAssessment, GuardianDecision
from agentic_trading.examiner import (
    ExamPlan, ExaminationError, examine, orders_digest, student_exam_history,
)
from agentic_trading.neural_training import train_student
from agentic_trading.simulator import QuoteBar, HistoricalOrder, ReplayCosts
from agentic_trading.storage import ExamRun, HistoricalDataset, TrainingCheckpoint
from test_neural_training import BASE, create_fixture, spec

START = BASE + timedelta(days=36)


def _bar(t: datetime, *, winning: bool = False, losing: bool = False):
    if winning:
        bid = ('100', '104', '99.5', '101')
    elif losing:
        bid = ('100', '101', '97', '99')
    else:
        bid = ('100', '101', '99.5', '100')
    ask = tuple(str(Decimal(x) + Decimal('0.2')) for x in bid)
    return QuoteBar(open_time=t, **dict(zip(('bid_open', 'bid_high', 'bid_low', 'bid_close',
                                             'ask_open', 'ask_high', 'ask_low', 'ask_close'), bid + ask)))


def _order(student_id: str, model_hash: str, at: datetime):
    p = TradeProposal(proposal_id=uuid4(), revision=1, student_id=UUID(student_id),
                      strategy_version='trend-s6-v1', model_sha256=model_hash,
                      instrument='XAUUSD', direction='LONG', entry_reference='100',
                      stop_price='98', target_price='103', tactic_id='trend', thesis='historical fixture',
                      invalidation='98 stop', observed_data_available_at=at,
                      created_at=at, expires_at=at+timedelta(minutes=3), content_sha256='b'*64)
    assessment = TradeAssessment(proposal_id=p.proposal_id, proposal_revision=1,
                                 proposal_sha256=p.content_sha256, scout_b_model_sha256='c'*64,
                                 expected_net_r='1.0', assessed_at=at+timedelta(seconds=1))
    guardian = GuardianDecision(proposal_id=p.proposal_id, proposal_revision=1,
                                proposal_sha256=p.content_sha256, decision='APPROVED',
                                reasons=('research limits',), decided_at=at+timedelta(seconds=2))
    return HistoricalOrder(proposal=p, assessment=assessment, guardian=guardian, quantity_oz='2')


def _costs():
    return ReplayCosts(commission_usd_per_oz_per_side='0.05', slippage_usd_per_oz_per_side='0.1',
                       max_spread_usd_per_oz='0.5', starting_equity_usd='10000',
                       max_position_oz='10', max_risk_fraction='0.05', max_leverage='2',
                       max_holding_minutes=10)


def _fixture(tmp_path, wins=70, total=101, incumbent=False):
    engine, factory, student_id = create_fixture(tmp_path)
    with factory() as session:
        training = spec(student_id)
        result = train_student(session, training, checkpoint_root=tmp_path/'weights')
        checkpoint_sha = result['metrics'][-1]['checkpoint_sha256']
        source = 'd'*64
        dataset = HistoricalDataset(source_hash=source, canonical_hash='e'*64,
            source_manifest={'instrument':'XAUUSD','timeframe':'M15','provider':'fixture-only'},
            quality_report={'rows': total * 3}, raw_path='never-qualifying-raw',
            canonical_path='never-qualifying-canonical', state='quarantined')
        session.add(dataset);session.commit()
        bars = []
        orders = []
        for i in range(total):
            at=START+timedelta(minutes=3*i)
            bars.extend([_bar(at), _bar(at+timedelta(minutes=1),winning=(i < wins),losing=(i >= wins)),
                         _bar(at+timedelta(minutes=2))])
            orders.append(_order(student_id, checkpoint_sha, at))
        orders=tuple(orders)
        incumbent_hash='f'*64 if incumbent else None
        incumbent_orders=tuple(_order(student_id, incumbent_hash, START+timedelta(minutes=3*i)) for i in range(total)) if incumbent else ()
        plan = ExamPlan(exam_id=uuid4(),student_id=UUID(student_id),training_run_id=training.run_id,
                        challenger_model_sha256=checkpoint_sha,challenger_orders_sha256=orders_digest(orders),
                        incumbent_model_sha256=incumbent_hash,
                        incumbent_orders_sha256=orders_digest(incumbent_orders) if incumbent else None,
                        dataset_id=UUID(dataset.id),source_sha256=source,tactic='trend',
                        train_cutoff=BASE+timedelta(days=34),holdout_start=START,
                        holdout_end=START+timedelta(minutes=3*total))
        return factory, student_id, plan, tuple(bars), orders, incumbent_orders


def _run(factory, tmp_path, plan, bars, orders, incumbent_orders=()):
    with factory() as session:
        return examine(session, plan, checkpoint_root=tmp_path/'weights',bars=bars,
                       challenger_orders=orders,incumbent_orders=incumbent_orders,costs=_costs())


def test_numerically_profitable_101_trades_still_unqualified(tmp_path):
    factory, sid, plan, bars, orders, inc=_fixture(tmp_path)
    result=_run(factory,tmp_path,plan,bars,orders,inc)
    assert result.challenger.closed_trades==101
    assert result.challenger.wins==70 and result.challenger.losses==31
    assert result.challenger.profit_factor > Decimal('1.2')
    assert result.numerical_thresholds_passed and result.challenger_outperformed
    assert result.verdict=='PROVISIONAL_NUMERIC_PASS'
    assert result.qualification=='unqualified'
    assert not result.research_promotion_allowed and not result.live_trading_allowed
    assert len(result.blockers)>=4
    second=_run(factory,tmp_path,plan,bars,orders,inc)
    assert result==second
    with factory() as session:
        history=student_exam_history(session,sid)
        assert len(history)==1 and history[0]['report_sha256']==result.report_sha256


def test_low_profitability_and_insufficient_closed_trades_fail(tmp_path):
    factory,sid,plan,bars,orders,inc=_fixture(tmp_path,wins=20,total=40)
    verdict=_run(factory,tmp_path,plan,bars,orders,inc)
    assert verdict.verdict=='PROVISIONAL_NUMERIC_FAIL'
    assert not verdict.numerical_thresholds_passed
    assert verdict.challenger.closed_trades==40


def test_tampered_order_snapshot_and_wrong_model_rejected(tmp_path):
    factory,sid,plan,bars,orders,inc=_fixture(tmp_path,total=3)
    with pytest.raises(ExaminationError,match='order snapshot'):
        _run(factory,tmp_path,plan,bars,orders[:-1])
    altered=orders[0].model_copy(update={'quantity_oz':Decimal('3')})
    with pytest.raises(ExaminationError,match='order snapshot'):
        _run(factory,tmp_path,plan,bars,(altered,)+orders[1:])
    plan2=plan.model_copy(update={'challenger_orders_sha256':orders_digest((altered,)+orders[1:])})
    assert _run(factory,tmp_path,plan2,bars,(altered,)+orders[1:]).qualification=='unqualified'


def test_model_checkpoint_tamper_rejected(tmp_path):
    factory,sid,plan,bars,orders,inc=_fixture(tmp_path,total=2)
    with factory() as session:
        row=session.scalar(select(TrainingCheckpoint).where(TrainingCheckpoint.run_id==str(plan.training_run_id))
                           .order_by(TrainingCheckpoint.epoch.desc()))
        (tmp_path/'weights'/row.relative_path).write_bytes(b'spoofed')
    with pytest.raises(ExaminationError,match='tampered'):
        _run(factory,tmp_path,plan,bars,orders)


def test_holdout_timing_and_out_of_scope_guardrails(tmp_path):
    factory,sid,plan,bars,orders,inc=_fixture(tmp_path,total=2)
    with pytest.raises(ValidationError,match='embargo'):
        ExamPlan.model_validate({**plan.model_dump(mode='python'),
                                 'train_cutoff':plan.holdout_start-timedelta(minutes=30)})
    with pytest.raises(ExaminationError,match='beyond the sealed'):
        _run(factory,tmp_path,plan,(bars[0].model_copy(update={'open_time':START-timedelta(minutes=1)}),)+bars[1:],orders)
    with pytest.raises(ExaminationError,match='market or tactic'):
        wrong=plan.model_copy(update={'tactic':'range'})
        _run(factory,tmp_path,wrong,bars,orders)


def test_dataset_unsupported_state_and_source_mismatch(tmp_path):
    factory,sid,plan,bars,orders,inc=_fixture(tmp_path,total=2)
    with factory() as session:
        d=session.get(HistoricalDataset,str(plan.dataset_id))
        d.state='verified'  # forged positive state is not supported
        session.commit()
    with pytest.raises(ExaminationError,match='not supported'):
        _run(factory,tmp_path,plan,bars,orders)
    with pytest.raises(ExaminationError,match='source provenance'):
        _run(factory,tmp_path,plan.model_copy(update={'source_sha256':'0'*64}),bars,orders)


def test_exam_idempotence_rejects_changed_results_and_detects_tamper(tmp_path):
    factory,sid,plan,bars,orders,inc=_fixture(tmp_path,total=2)
    first=_run(factory,tmp_path,plan,bars,orders)
    with pytest.raises(ExaminationError,match='exam ID reused'):
        _run(factory,tmp_path,plan,bars[:-1],orders)
    with factory() as session:
        row=session.get(ExamRun,str(plan.exam_id))
        row.report['verdict']='PROVISIONAL_NUMERIC_PASS'
        # SQLAlchemy JSON in-place change may be untracked: assign new dict
        row.report={**row.report, 'verdict':'PROVISIONAL_NUMERIC_PASS', 'blockers': []}
        session.commit()
        with pytest.raises(ExaminationError,match='checksum'):
            student_exam_history(session,sid)


def test_incumbent_same_market_identical_tape_and_costs(tmp_path):
    factory,sid,plan,bars,orders,inc=_fixture(tmp_path,total=3,incumbent=True)
    verdict=_run(factory,tmp_path,plan,bars,orders,inc)
    assert verdict.incumbent.closed_trades==3
    assert not verdict.challenger_outperformed if verdict.challenger.net_pnl_usd == verdict.incumbent.net_pnl_usd else True
    assert verdict.configuration_sha256 and verdict.quote_stream_sha256


def test_no_training_permission_or_promotion_api(tmp_path):
    from agentic_trading.api import create_app
    from fastapi.testclient import TestClient
    from agentic_trading.settings import Settings
    client=TestClient(create_app(Settings(database_url=f"sqlite:///{tmp_path/'api.db'}", secret_key='test-secret')))
    for endpoint in ('/v1/exams/run','/v1/research/promote','/v1/orders'):
        assert client.post(endpoint,json={}).status_code==404
    assert client.get('/v1/students/random/exams').status_code==401
