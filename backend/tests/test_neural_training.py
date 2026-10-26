"""Sprint 6: neural training/checkpoints on synthetic closed trade fixtures only."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from agentic_trading.neural_training import (TrainingError, TrainingSpec, freeze_training_data,
    load_checkpoint, train_student, student_training_runs, FEATURE_NAMES)
from agentic_trading.skills_memory import ClosedTradeEpisode, Origin, ExamPartition, append_episode
from agentic_trading.storage import (Base, LearningPlan, Student, TrainingRun, TrainingCheckpoint,
                                     new_session_factory)

BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def create_fixture(tmp_path, count=26, *, directed=True, alternating=True):
    engine, factory = new_session_factory(f'sqlite:///{tmp_path / "s6.sqlite3"}')
    Base.metadata.create_all(engine)
    with factory() as session:
        student = Student(name='Orion', name_key='orion')
        session.add(student)
        session.flush()
        session.add(LearningPlan(student_id=student.id, version=1, mode='directed' if directed else 'autonomous',
                                 markets=['XAUUSD'] if directed else [], skills=['trend'] if directed else [], reason='S6 training'))
        for i in range(count):
            at = BASE + timedelta(days=i)
            source = f'fixture:day-{i}'
            e = ClosedTradeEpisode(event_id=uuid4(), student_id=UUID(student.id), source_id=source,
                source_sha256=sha256(source.encode()).hexdigest(), origin=Origin.SYNTHETIC_FIXTURE,
                partition=ExamPartition.TRAIN, instrument='XAUUSD', strategy_version='trend-s6-v1',
                proposal_sha256='b'*64,
                skill_ids=('market:XAUUSD','risk:risk_management','tactic:trend'),
                signal_at=at, opened_at=at + timedelta(minutes=1), closed_at=at + timedelta(minutes=19),
                available_at=at + timedelta(minutes=20), initial_risk_usd=Decimal('10'),
                gross_pnl_usd=Decimal('20' if not alternating or i%2 else '0'),
                spread_cost_usd=Decimal('1'), slippage_cost_usd=Decimal('1'), fees_usd=Decimal('1'),
                mfe_r=Decimal('2'), mae_r=Decimal('1'),
                close_reason='closed', market_regime=('TREND_UP' if i%2 else 'RANGE'))
            append_episode(session,e)
        session.commit()
        id_ = student.id
    return engine, factory, id_


def spec(sid, **kwargs):
    d = dict(run_id=uuid4(), student_id=UUID(sid), plan_version=1, as_of=BASE+timedelta(days=33),
             market='XAUUSD', tactic='trend', epochs=5, learning_rate=0.03, seed=123)
    d.update(kwargs)
    return TrainingSpec(**d)


def test_snapshot_no_future_or_sealed_or_other_students(tmp_path):
    _,factory,sid=create_fixture(tmp_path)
    with factory() as session:
        future = spec(sid, as_of=BASE+timedelta(days=15))
        data=freeze_training_data(session,future)
        assert len(data['train'])+len(data['validation']) <= 16
        assert all(row['available_at'] <= future.as_of for row in data['train']+data['validation'])
        other=Student(name='Nova', name_key='nova')
        session.add(other);session.flush()
        src='fixture:holdout'
        sample=ClosedTradeEpisode(event_id=uuid4(),student_id=UUID(sid),source_id=src,
            source_sha256=sha256(src.encode()).hexdigest(),origin=Origin.SYNTHETIC_FIXTURE,
            partition=ExamPartition.HOLDOUT,instrument='XAUUSD',strategy_version='holdout',
            proposal_sha256='c'*64,skill_ids=('market:XAUUSD','risk:risk_management','tactic:trend'),
            signal_at=BASE+timedelta(days=30),opened_at=BASE+timedelta(days=30,minutes=1),
            closed_at=BASE+timedelta(days=30,minutes=5),available_at=BASE+timedelta(days=30,minutes=6),
            initial_risk_usd=Decimal('10'),gross_pnl_usd=Decimal('5000'),spread_cost_usd=Decimal('1'),
            slippage_cost_usd=Decimal('1'),fees_usd=Decimal('1'),mfe_r=Decimal('100'),mae_r=Decimal('0'),
            close_reason='holdout',market_regime='TREND_UP')
        append_episode(session,sample);session.commit()
        data=freeze_training_data(session,spec(sid))
        assert len(data['train'])+len(data['validation'])==26
        assert str(sample.event_id) not in data['manifest']['train_event_ids']
        assert str(sample.event_id) not in data['manifest']['development_validation_event_ids']
        assert all(len(row['features'])==len(FEATURE_NAMES) for row in data['train'])
        assert all('net_pnl' not in str(row['features']) for row in data['train'])
        assert data['provenance']==['synthetic_fixture']


def test_train_restart_continues_and_is_bitwise_reproducible(tmp_path):
    _, factory, sid = create_fixture(tmp_path)
    s=spec(sid)
    with factory() as session:
        two=train_student(session,s,checkpoint_root=tmp_path/'weights',stop_after_epoch=2)
        assert two['epoch']==2
        assert len(two['metrics'])==2
        resumed=train_student(session,s,checkpoint_root=tmp_path/'weights')
        assert resumed['epoch']==5
        assert resumed['qualification']=='unqualified' and not resumed['research_eligible']
        assert len(resumed['metrics'])==5
        second=train_student(session,s,checkpoint_root=tmp_path/'weights')
        assert second==resumed
        other=train_student(session,spec(sid),checkpoint_root=tmp_path/'weights')
        assert [r['checkpoint_sha256'] for r in other['metrics']] == [r['checkpoint_sha256'] for r in resumed['metrics']]
        assert len(student_training_runs(session,sid))==2


def test_changing_config_or_frozen_examples_rejects_resume(tmp_path):
    _,factory,sid=create_fixture(tmp_path)
    s=spec(sid)
    with factory() as session:
        train_student(session,s,checkpoint_root=tmp_path/'weights',stop_after_epoch=2)
        with pytest.raises(TrainingError, match='collision'):
            train_student(session,s.model_copy(update={'learning_rate':0.02}),checkpoint_root=tmp_path/'weights')
        episode=session.scalar(select(__import__('agentic_trading.storage',fromlist=['TradeExperience']).TradeExperience))
        episode.net_r='999'
        session.commit()
        with pytest.raises(TrainingError, match='archive|mismatch|integrity'):
            train_student(session,s,checkpoint_root=tmp_path/'weights')


def test_tamper_checkpoint_rejected_and_no_pickle_executed(tmp_path):
    import torch
    _,factory,sid=create_fixture(tmp_path)
    s=spec(sid)
    with factory() as session:
        train_student(session,s,checkpoint_root=tmp_path/'weights',stop_after_epoch=2)
        latest=session.scalar(select(TrainingCheckpoint).where(TrainingCheckpoint.run_id==str(s.run_id))
                             .order_by(TrainingCheckpoint.epoch.desc()))
        destination=tmp_path/'weights'/latest.relative_path
        destination.write_bytes(b'not-valid-model')
        with pytest.raises(TrainingError, match='checksum'):
            train_student(session,s,checkpoint_root=tmp_path/'weights')
        with pytest.raises(TrainingError, match='outside'):
            load_checkpoint(torch,tmp_path/'weights',type('Record',(),{
              'relative_path':'../../outside','artifact_sha256':'0'*64})(),
              __import__('agentic_trading.neural_training',fromlist=['_model'])._model(torch))


def test_fail_closed_missing_evidence_or_wrong_learning_direction(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=11)
    with factory() as session:
        with pytest.raises(TrainingError,match='insufficient'):
            train_student(session,spec(sid),checkpoint_root=tmp_path/'weights')
        with pytest.raises(TrainingError,match='outside CEO'):
            freeze_training_data(session,spec(sid,market='EURUSD'))
        with pytest.raises(TrainingError,match='synthetic'):
            freeze_training_data(session,spec(sid,allow_synthetic_research=False))
    with pytest.raises(ValidationError, match='UTC'):
        spec(sid,as_of=datetime(2025,1,1))


def test_checkpoints_tracked_per_student_and_not_qualified(tmp_path):
    _,factory,sid=create_fixture(tmp_path)
    with factory() as session:
        result=train_student(session,spec(sid),checkpoint_root=tmp_path/'weights')
        assert session.scalar(select(TrainingRun)).qualification=='unqualified'
        assert session.query(TrainingCheckpoint).count()==5
        outputs=student_training_runs(session,sid)
        assert outputs[0]['qualification']=='unqualified'
        assert outputs[0]['research_eligible'] is False
        assert student_training_runs(session,str(uuid4()))==[]
        run=session.get(TrainingRun,result['run_id'])
        run.snapshot_manifest['schema']='tampered'
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(run,'snapshot_manifest');session.commit()
        with pytest.raises(TrainingError,match='integrity'):
            student_training_runs(session,sid)


def test_readonly_authenticated_training_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from agentic_trading.api import create_app
    from agentic_trading.auth import password_hash
    from agentic_trading.settings import Settings
    from agentic_trading.storage import CEO
    engine, factory, sid = create_fixture(tmp_path)
    with factory() as session:
        session.add(CEO(email='s6@example.org', password_hash=password_hash('long-local-password')))
        session.commit()
    cfg=Settings(database_url=f'sqlite:///{tmp_path / "s6.sqlite3"}',secret_key='L'*48)
    client=TestClient(create_app(cfg))
    assert client.get(f'/v1/students/{sid}/training').status_code==401
    assert client.post(f'/v1/students/{sid}/training').status_code==405
    assert client.post('/v1/auth/login', json={'email':'s6@example.org','password':'long-local-password'}).status_code==200
    empty=client.get(f'/v1/students/{sid}/training')
    assert empty.status_code==200 and empty.json()['runs']==[]
    assert client.get(f'/v1/students/{sid}/training?limit=999').status_code==422
    assert client.get(f'/v1/students/{uuid4()}/training').status_code==404
    with factory() as session:
        train_student(session,spec(sid),checkpoint_root=tmp_path/'weights')
    response=client.get(f'/v1/students/{sid}/training')
    assert response.status_code==200
    assert len(response.json()['runs'])==1
    assert response.json()['runs'][0]['research_eligible'] is False
    assert len(response.json()['runs'][0]['metrics'])==5
    assert client.get('/v1/capabilities').json()['automatic_training_enabled'] is False
    assert client.post('/v1/training/run').status_code==404
    engine.dispose()
