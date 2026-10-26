"""Sprint 6: provenance gating, time-safe learning, deterministic recovery, CEO read-only reporting."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentic_trading.api import create_app
from agentic_trading.auth import password_hash
from agentic_trading.neural_training import (
    TrainingSettings, NeuralTrainingError, TrainingPaused, run_fixture_training,
    student_training_history, _eligible, _vector,
)
from agentic_trading.settings import Settings
from agentic_trading.skills_memory import (
    ClosedTradeEpisode, Origin, ExamPartition, append_episode,
)
from agentic_trading.storage import Base, CEO, Student, LearningPlan, TrainingRun, new_session_factory

TORCH = pytest.importorskip('torch', reason='optional PyTorch worker dependency')
pytestmark = pytest.mark.neural
AT = datetime(2025, 5, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def fixture_db(tmp_path):
    cfg = Settings(database_url=f"sqlite:///{tmp_path/'train.sqlite3'}", secret_key='K' * 40,
                   data_dir=str(tmp_path/'checkpoints'))
    engine, factory = new_session_factory(cfg.database_url)
    Base.metadata.create_all(engine)
    with factory() as db:
        student = Student(name='Orion', name_key='orion')
        second = Student(name='Nova', name_key='nova')
        db.add_all([student, second])
        db.flush()
        db.add_all([
            LearningPlan(student_id=student.id, version=1, mode='directed', markets=['XAUUSD'],
                         skills=['trend'], reason='CEO assigned Gold'),
            LearningPlan(student_id=second.id, version=1, mode='autonomous', markets=[], skills=[],
                         reason='Automatic direction'),
            CEO(email='owner@example.org', password_hash=password_hash('training-test-password')),
        ])
        db.commit()
        ids = (student.id, second.id)
    yield cfg, factory, ids
    engine.dispose()


def build_episode(student: str, n: int, *, partition=ExamPartition.TRAIN,
                  origin=Origin.SYNTHETIC_FIXTURE, tactic='trend', available=None,
                  market='XAUUSD', source_id='fixture:neural') -> ClosedTradeEpisode:
    signal = AT + timedelta(hours=n*2)
    close = signal + timedelta(minutes=30)
    return ClosedTradeEpisode(
        event_id=uuid4(), student_id=UUID(student), source_id=source_id,
        source_sha256='f'*64, origin=origin, partition=partition,
        instrument=market, strategy_version='gold-trend-v1', proposal_sha256='a'*64,
        skill_ids=(f'market:{market}', 'risk:risk_management', f'tactic:{tactic}'),
        signal_at=signal, opened_at=signal+timedelta(minutes=1), closed_at=close,
        available_at=available or close+timedelta(minutes=1),
        initial_risk_usd=Decimal('10'), gross_pnl_usd=Decimal('35') if n % 3 else Decimal('-13'),
        spread_cost_usd=Decimal('2'), slippage_cost_usd=Decimal('1'), fees_usd=Decimal('2'),
        mfe_r=Decimal('3'), mae_r=Decimal('.5'), close_reason='closed',
        market_regime='TREND_UP' if n % 2 else 'RANGE',
    )


def add_episodes(factory, student, count=24):
    with factory() as db:
        for i in range(count):
            append_episode(db, build_episode(student, i))
        db.commit()


def config(student, **changes):
    values = {'student_id': student, 'market': 'XAUUSD', 'tactic': 'trend',
              'as_of': AT + timedelta(days=6), 'epochs': 4, 'seed': 91}
    values.update(changes)
    return TrainingSettings(**values)


def train(db, cfg, storage, **kwargs):
    return run_fixture_training(db, storage, cfg, environment='development',
                                explicit_fixture_authorisation=True, **kwargs)


def test_run_isolation_financial_supervised_targets_and_registry(fixture_db):
    cfg, factory, (sid, other) = fixture_db
    add_episodes(factory, sid)
    with factory() as db:
        result = train(db, config(sid), Path(cfg.data_dir))
        assert result['student_id'] == sid
        assert result['epochs_completed'] == 4
        assert result['train_examples'] == 18 and result['validation_examples'] == 6
        assert result['purged_count'] == 0
        assert len(result['curve']) == 4
        assert all(set(point) == {'epoch','train_loss','validation_loss'} for point in result['curve'])
        assert result['origin'] == 'synthetic_fixture'
        assert result['exam_eligible'] is False
        assert result['research_eligible'] is False
        assert result['qualification'] == 'unqualified'
        assert len(db.scalars(select(TrainingRun)).all()) == 1
        assert student_training_history(db, other, Path(cfg.data_dir))['runs'] == []


def test_stop_after_epoch_resume_matches_uninterrupted_weights(fixture_db, tmp_path):
    cfg, factory, (sid, _) = fixture_db
    add_episodes(factory, sid)
    folder=Path(cfg.data_dir)
    with factory() as db:
        with pytest.raises(TrainingPaused, match='epoch 2'):
            train(db, config(sid), folder, interrupt_after_epoch=2)
        assert not db.scalars(select(TrainingRun)).all()
    # Copy the pre-registration database into an independent research workspace.
    clone = tmp_path / 'fresh.sqlite3'
    with sqlite3.connect(Path(cfg.database_url.removeprefix('sqlite:///'))) as src, sqlite3.connect(clone) as dst:
        src.backup(dst)
    clone_engine, clone_factory = new_session_factory(f'sqlite:///{clone}')
    try:
        with clone_factory() as db:
            independent=train(db, config(sid), tmp_path/'independent')
    finally:
        clone_engine.dispose()
    with factory() as db:
        resumed=train(db, config(sid), folder)
        same=train(db, config(sid), folder)
        assert resumed['checkpoint_sha256']==same['checkpoint_sha256']
        assert len(db.scalars(select(TrainingRun)).all())==1
        assert resumed['checkpoint_sha256']==independent['checkpoint_sha256']
        assert resumed['curve']==independent['curve']


def test_tampered_checkpoint_and_registry_refuse_history(fixture_db):
    cfg, factory, (sid, _) = fixture_db
    add_episodes(factory,sid)
    with factory() as db:
        result=train(db, config(sid), Path(cfg.data_dir))
        record=db.scalar(select(TrainingRun))
        path=Path(cfg.data_dir)/record.checkpoint_path
        data=json.loads(path.read_text())
        data['payload']['weights']['0.bias'][0]=999.0
        path.write_text(json.dumps(data))
        with pytest.raises(NeuralTrainingError, match='checkpoint'):
            student_training_history(db,sid,Path(cfg.data_dir))
        with pytest.raises(NeuralTrainingError, match='checkpoint'):
            train(db,config(sid),Path(cfg.data_dir))


def test_time_safe_partition_purge_and_no_outcome_input(fixture_db):
    cfg, factory, (sid, _) = fixture_db
    add_episodes(factory,sid)
    with factory() as db:
        normal = _eligible(db, config(sid))
        assert len(normal[1])==18 and len(normal[2])==6
        delayed = build_episode(sid, 4, available=AT+timedelta(days=3))
        append_episode(db, delayed)
        # This later-known outcome cannot enter the training partition even if the
        # trade's signal timestamp preceded the first validation signal.
        db.commit()
        purged = _eligible(db, config(sid))
        assert delayed.event_id not in {e.event_id for e in purged[1]}
        assert len(purged[1]) <= 18
        holdout=build_episode(sid,29,partition=ExamPartition.HOLDOUT)
        append_episode(db,holdout)
        db.commit()
        still=_eligible(db,config(sid))
        assert holdout.event_id not in {e.event_id for e in still[1]+still[2]}
        a=build_episode(sid,1)
        b=a.model_copy(update={'gross_pnl_usd': Decimal('999999')})
        assert _vector(a)==_vector(b), 'post-close financial outcome leaked into feature input'


def test_quarantined_data_cannot_be_trained(fixture_db):
    cfg,factory,(sid,_)=fixture_db
    add_episodes(factory,sid)
    with factory() as db:
        # A malicious record with a real-looking source cannot silently train.
        row=db.scalar(select(__import__('agentic_trading.storage',fromlist=['TradeExperience']).TradeExperience))
        content=dict(row.payload)
        content['origin']='historical_quarantined'
        from agentic_trading.skills_memory import ClosedTradeEpisode
        replacement=ClosedTradeEpisode.model_validate(content)
        row.origin='historical_quarantined'
        row.payload=content
        row.payload_hash=replacement.content_sha256
        db.commit()
        with pytest.raises(NeuralTrainingError,match='quarantined'):
            train(db,config(sid),Path(cfg.data_dir))


def test_reject_without_explicit_development_authority_and_scope(fixture_db):
    cfg,factory,(sid,_)=fixture_db
    add_episodes(factory,sid)
    with factory() as db:
        with pytest.raises(NeuralTrainingError,match='authorisation'):
            run_fixture_training(db,Path(cfg.data_dir),config(sid),environment='production',explicit_fixture_authorisation=True)
        with pytest.raises(NeuralTrainingError,match='authorisation'):
            run_fixture_training(db,Path(cfg.data_dir),config(sid),environment='development')
        with pytest.raises(NeuralTrainingError,match='scope'):
            train(db,config(sid,tactic='breakout'),Path(cfg.data_dir))
        with pytest.raises(NeuralTrainingError,match='epochs'):
            config(sid,epochs=999)
        with pytest.raises(NeuralTrainingError,match='rate'):
            config(sid,learning_rate=float('nan'))


def test_ceo_training_readonly_and_no_model_deployment_routes(fixture_db):
    cfg,factory,(sid,_)=fixture_db
    add_episodes(factory,sid)
    client=TestClient(create_app(cfg))
    assert client.get(f'/v1/students/{sid}/training').status_code==401
    login=client.post('/v1/auth/login',json={'email':'owner@example.org','password':'training-test-password'})
    assert login.status_code==200
    assert client.get(f'/v1/students/{sid}/training').json()['runs']==[]
    with factory() as db:
        train(db,config(sid),Path(cfg.data_dir))
    results=client.get(f'/v1/students/{sid}/training')
    assert results.status_code==200 and len(results.json()['runs'])==1
    assert results.json()['runs'][0]['qualification']=='unqualified'
    assert client.post(f'/v1/students/{sid}/training',json={}).status_code==405
    assert client.get('/v1/capabilities').json()['training_api_enabled'] is False
    assert client.get('/v1/capabilities').json()['paper_trading_enabled'] is False
    assert client.get('/v1/capabilities').json()['live_trading_enabled'] is False
    assert not any('/orders' in route.path or '/broker' in route.path for route in client.app.routes)
