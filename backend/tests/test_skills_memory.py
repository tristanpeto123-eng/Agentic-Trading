"""Sprint 5: closed outcomes, provenance, immutable journal, no leakage or fake mastery."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from agentic_trading.api import create_app
from agentic_trading.auth import password_hash
from agentic_trading.settings import Settings
from agentic_trading.skills_memory import (
    ClosedTradeEpisode, ExamPartition, Origin, MemoryError, append_episode,
    recall_training_examples, read_student_memory, student_skill_progress, catalog_manifest,
)
from agentic_trading.storage import Base, CEO, Student, LearningPlan, HistoricalDataset, TradeExperience, new_session_factory

START = datetime(2025, 8, 4, 9, tzinfo=timezone.utc)
SRC = 'a'*64
PROPOSAL = 'b'*64


def episode(student_id, *, event_id=None, signal_at=START, opened_at=None, closed_at=None,
            available_at=None, gross='20', spread='3', slip='2', fees='5',
            source_id='fixture:demo1', origin=Origin.SYNTHETIC_FIXTURE,
            partition=ExamPartition.TRAIN, source_sha256=SRC, skill_ids=None):
    opened = opened_at or signal_at + timedelta(minutes=1)
    closed = closed_at or opened + timedelta(minutes=15)
    return ClosedTradeEpisode(
        event_id=event_id or uuid4(), student_id=student_id,
        source_id=source_id, source_sha256=source_sha256, origin=origin, partition=partition,
        instrument='XAUUSD', strategy_version='gold-trend-v1', proposal_sha256=PROPOSAL,
        skill_ids=skill_ids or ('market:XAUUSD', 'risk:risk_management', 'tactic:trend'),
        signal_at=signal_at, opened_at=opened, closed_at=closed,
        available_at=available_at or closed + timedelta(minutes=1),
        initial_risk_usd=Decimal('10'), gross_pnl_usd=Decimal(gross),
        spread_cost_usd=Decimal(spread), slippage_cost_usd=Decimal(slip), fees_usd=Decimal(fees),
        mfe_r=Decimal('2.5'), mae_r=Decimal('0.5'), close_reason='target', market_regime='TREND_UP',
    )


@pytest.fixture
def setup(tmp_path):
    cfg = Settings(database_url=f"sqlite:///{tmp_path / 'new.sqlite3'}", secret_key='R'*48)
    engine, session_factory = new_session_factory(cfg.database_url)
    Base.metadata.create_all(engine)
    with session_factory() as session:
        student = Student(name='Orion', name_key='orion')
        session.add(student)
        session.flush()
        session.add(LearningPlan(student_id=student.id, version=1, mode='directed',
                                 markets=['XAUUSD'], skills=['trend'], reason='Initial'))
        session.add(CEO(email='owner@example.org', password_hash=password_hash('long-local-test-password')))
        session.commit()
        student_id = student.id
    engine.dispose()
    return cfg, student_id, session_factory


def test_catalog_versions_prerequisites_and_deterministic_hash():
    info = catalog_manifest()
    assert info['catalog_sha256'] == catalog_manifest()['catalog_sha256']
    assert {s['id'] for s in info['skills']} >= {'market:XAUUSD', 'tactic:trend', 'risk:risk_management'}
    assert next(s for s in info['skills'] if s['id'] == 'tactic:trend')['prerequisite_ids'] == ['risk:risk_management']


def test_costs_determine_good_bad_flat_not_gross_profit():
    sid=uuid4()
    good=episode(sid)
    bad=episode(sid,gross='6')
    flat=episode(sid,gross='10')
    assert good.outcome.value == 'good' and good.net_pnl_usd == Decimal('10') and good.net_r == Decimal('1')
    assert bad.outcome.value == 'bad' and bad.net_pnl_usd == Decimal('-4')
    assert flat.outcome.value == 'flat' and flat.net_r == 0


def test_reject_future_episode_missing_prereqs_invalid_market_and_timezones():
    sid=uuid4()
    with pytest.raises(ValidationError, match='after its trade is closed'):
        episode(sid, available_at=START + timedelta(minutes=2))
    with pytest.raises(ValidationError, match='prerequisite'):
        episode(sid, skill_ids=('market:XAUUSD', 'tactic:trend'))
    with pytest.raises(ValidationError, match='market skill'):
        episode(sid, skill_ids=('market:EURUSD', 'risk:risk_management', 'tactic:trend'))
    with pytest.raises(ValidationError, match='UTC'):
        episode(sid, signal_at=START.replace(tzinfo=None))
    with pytest.raises(ValidationError, match='finite'):
        episode(sid, gross='NaN')


def test_append_idempotent_content_hash_and_conflicting_event_fail(setup):
    _, sid, factory=setup
    e=episode(UUID(sid))
    with factory() as session:
        first=append_episode(session,e)
        session.commit()
        assert append_episode(session,e).id == first.id
        with pytest.raises(MemoryError, match='collision'):
            append_episode(session,episode(e.student_id, event_id=e.event_id, gross='50'))
        assert len(session.scalars(select(TradeExperience)).all()) == 1


def test_recall_is_asof_scoped_and_no_holdout_or_validation_leakage(setup):
    _, sid, factory=setup
    student_id=UUID(sid)
    early=episode(student_id)
    future=episode(student_id,signal_at=START+timedelta(days=1))
    holdout=episode(student_id,partition=ExamPartition.HOLDOUT)
    validation=episode(student_id,partition=ExamPartition.VALIDATION)
    with factory() as session:
        for e in (early,future,holdout,validation):
            append_episode(session,e)
        session.commit()
        recalled=recall_training_examples(session,sid,as_of=START+timedelta(hours=1),skill_ids=('tactic:trend',))
        assert [r['event_id'] for r in recalled] == [str(early.event_id)]
        assert recalled[0]['research_qualified'] is False
        assert recall_training_examples(session,sid,as_of=START+timedelta(days=2),exclude_source_sha256=SRC) == []
        assert recall_training_examples(session,sid,as_of=START+timedelta(hours=1),market_regime='CHOP') == []
        assert len(read_student_memory(session,sid)) == 4
        with pytest.raises(ValueError, match='UTC'):
            recall_training_examples(session,sid,as_of=datetime(2025,8,4))


def test_mastery_not_conferred_and_study_targets_not_skill_proof(setup):
    _, sid, factory=setup
    with factory() as session:
        student=session.get(Student,sid)
        summary=student_skill_progress(session, student)
        assert summary['qualification'] == 'unqualified'
        assert any(s['target'] and s['experience_count']==0 and s['mastery_status']=='unassessed'
                   for s in summary['skills'])
        append_episode(session, episode(UUID(sid)))
        session.commit()
        summary=student_skill_progress(session,student)
        assert all(s['mastery_status']=='unassessed' and not s['research_qualified'] for s in summary['skills'])
        assert next(s for s in summary['skills'] if s['skill_id']=='tactic:trend')['good']==1


def test_historical_origin_must_match_existing_quarantined_dataset(setup):
    _, sid, factory=setup
    with factory() as session:
        e=episode(UUID(sid),source_id='fake',origin=Origin.HISTORICAL_QUARANTINED)
        with pytest.raises(MemoryError,match='provenance'):
            append_episode(session,e)
        ds=HistoricalDataset(source_hash=SRC, canonical_hash='c'*64,
            source_manifest={'instrument':'XAUUSD','timeframe':'M15','provider':'test'},
            quality_report={},raw_path='a',canonical_path='b',state='quarantined')
        session.add(ds)
        session.flush()
        e=episode(UUID(sid),source_id=ds.id,origin=Origin.HISTORICAL_QUARANTINED)
        append_episode(session,e)
        session.commit()
        assert read_student_memory(session,sid)[0]['origin']=='historical_quarantined'
        assert read_student_memory(session,sid)[0]['research_qualified'] is False


def test_tampered_archive_fails_closed_even_if_payload_looks_profitable(setup):
    _, sid, factory=setup
    with factory() as session:
        e=episode(UUID(sid))
        append_episode(session,e)
        session.commit()
        row=session.get(TradeExperience,str(e.event_id))
        row.payload={**row.payload,'gross_pnl_usd':'999999'}
        session.commit()
        with pytest.raises(MemoryError,match='integrity'):
            read_student_memory(session,sid)


def test_api_read_only_ceo_and_no_write_routes(setup):
    cfg,sid,factory=setup
    api=TestClient(create_app(cfg))
    assert api.get('/v1/skills/catalog').status_code==401
    assert api.get(f'/v1/students/{sid}/memory').status_code==401
    login=api.post('/v1/auth/login',json={'email':'owner@example.org','password':'long-local-test-password'})
    assert login.status_code==200
    catalog=api.get('/v1/skills/catalog').json()
    assert 'catalog_sha256' in catalog
    assert api.get(f'/v1/students/{sid}/skills').json()['qualification']=='unqualified'
    assert api.get(f'/v1/students/{sid}/memory').json()['episodes']==[]
    assert api.get(f'/v1/students/{uuid4()}/memory').status_code==404
    assert api.get(f'/v1/students/{sid}/memory?limit=1000').status_code==422
    assert api.post(f'/v1/students/{sid}/memory',json={}).status_code==405
    assert api.get('/v1/capabilities').json()['automatic_memory_ingest_enabled'] is False
    with factory() as session:
        append_episode(session,episode(UUID(sid)))
        session.commit()
    assert len(api.get(f'/v1/students/{sid}/memory').json()['episodes'])==1
    assert api.get(f'/v1/students/{sid}/skills').json()['skills'][0]['research_qualified'] is False


def test_reject_wrong_student_and_fake_origin(setup):
    _, sid, factory=setup
    with factory() as session:
        with pytest.raises(MemoryError,match='unknown student'):
            append_episode(session,episode(uuid4()))
        with pytest.raises(MemoryError,match='identify their fixture'):
            append_episode(session, episode(UUID(sid),source_id='unverified-download'))


def test_students_have_isolated_memories_and_no_cross_student_recall(setup):
    _, sid, factory = setup
    with factory() as session:
        another = Student(name='Nova', name_key='nova')
        session.add(another)
        session.flush()
        session.add(LearningPlan(student_id=another.id, version=1, mode='autonomous',
                                 markets=[], skills=[], reason='Initial'))
        append_episode(session, episode(UUID(sid)))
        session.commit()
        assert read_student_memory(session, another.id) == []
        assert recall_training_examples(session, another.id, as_of=START + timedelta(days=1)) == []
        assert len(read_student_memory(session, sid)) == 1


def test_tampered_index_and_invalid_payload_are_rejected(setup):
    _, sid, factory = setup
    with factory() as session:
        event = episode(UUID(sid))
        append_episode(session, event)
        session.commit()
        row = session.get(TradeExperience, str(event.event_id))
        row.net_pnl_usd = '1000000'
        session.commit()
        with pytest.raises(MemoryError, match='integrity'):
            read_student_memory(session, sid)
        row.net_pnl_usd = str(event.net_pnl_usd)
        row.payload = {**row.payload, 'opened_at': 'not-a-date'}
        session.commit()
        with pytest.raises(MemoryError, match='invalid or tampered'):
            read_student_memory(session, sid)


def test_memory_survives_database_reopen_and_plan_switch(setup):
    cfg, sid, factory = setup
    with factory() as session:
        append_episode(session, episode(UUID(sid)))
        session.add(LearningPlan(student_id=sid, version=2, mode='autonomous',
                                 markets=[], skills=[], reason='CEO changed direction'))
        session.commit()
    engine, reopened = new_session_factory(cfg.database_url)
    with reopened() as session:
        assert len(read_student_memory(session,sid)) == 1
        student = session.get(Student,sid)
        skills = student_skill_progress(session,student)['skills']
        trend = next(x for x in skills if x['skill_id'] == 'tactic:trend')
        assert trend['target'] is False
        assert trend['experience_count'] == 1
    engine.dispose()
