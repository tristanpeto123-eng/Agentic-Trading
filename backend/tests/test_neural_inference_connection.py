"""Neural checkpoint -> strategy signal -> S4 diagnostic trace, never live orders."""
from datetime import datetime, timedelta, timezone
import importlib

import numpy as np
import pytest
from sqlalchemy import select

from agentic_trading.research_neural import (
    ResearchNeuralError, _closed_signal_features, build_training_snapshot,
    create_run, get_run_report, load_neural_inference, score_neural_candidate,
    train_one_epoch,
)
from agentic_trading.research_trace import TraceBatchInput, NeuralPredictionInput, inspect_trace_batch
from agentic_trading.storage import Base, LearningPlan, ResearchNeuralEpoch, Student, new_session_factory
from test_research_neural import research_bars
from test_historical_render import _setup, _source


def student(factory, name='Neural Inference', market='XAUUSD'):
    with factory() as session:
        student=Student(name=name, name_key=name.lower())
        session.add(student);session.flush()
        session.add(LearningPlan(student_id=student.id, version=1, mode='directed',
                                 markets=[market], skills=['trend'], reason='Neural research'))
        session.commit()
        return student.id


def saved_model(session, sid, bars, market='XAUUSD'):
    obj=create_run(session,sid,market=market,tactic='trend',plan_version=1,
                   bars=bars,source_sha256='a'*64)
    train_one_epoch(session,sid,obj['run_id'],0)
    return load_neural_inference(session,sid,plan_version=1)


def test_checkpoint_prediction_matches_training_features_no_lookahead(tmp_path):
    engine,factory=new_session_factory('sqlite:///'+str(tmp_path/'infer.db'))
    Base.metadata.create_all(engine)
    sid=student(factory)
    bars=research_bars()
    with factory() as session:
        context=saved_model(session,sid,bars)
        assert context['weights_sha256'] and context['epoch']==1
        first=build_training_snapshot(bars,market='XAUUSD',tactic='trend',
            source_sha256='a'*64,plan_version=1)['train'][0]
        at=datetime.fromisoformat(first['at'])
        n=next(i for i,b in enumerate(bars)
               if datetime.fromisoformat(b['open_time'].replace('Z','+00:00'))==at)
        features,observed=_closed_signal_features(bars[n-4:n+1],
            'XAUUSD','trend',context['origin'])
        assert np.allclose(features, first['f'],atol=1e-13)
        assert observed.isoformat()==datetime.fromisoformat(bars[n]['available_at'].replace('Z','+00:00')).isoformat()
        at_index=1250
        current=score_neural_candidate(context,bars[at_index-4:at_index+1],
             market='XAUUSD',tactic='trend')
        assert current['status']=='INFERENCE_AVAILABLE'
        assert current['epoch']==1
        assert current['checkpoint_sha256']==context['weights_sha256']
        assert current['time_scope']=='POST_DEVELOPMENT_UNVALIDATED'
        assert 0<=current['probability_profit_raw']<=1
        assert current['guardian_authorised'] is False
        changed=bars[at_index+1].copy()
        changed['close']='999999'
        bars[at_index+1]=changed
        assert score_neural_candidate(context,bars[at_index-4:at_index+1],
                 market='XAUUSD',tactic='trend') == current
        assert score_neural_candidate(context,bars[at_index-4:at_index+1],
                 market='BTCUSD',tactic='trend')['status']=='MODEL_SCOPE_MISMATCH'
    engine.dispose()


def test_frozen_neural_model_refuses_wrong_student_plan_missing_or_corrupt_weights(tmp_path):
    engine,factory=new_session_factory('sqlite:///'+str(tmp_path/'infer.db'))
    Base.metadata.create_all(engine)
    sid=student(factory)
    with factory() as session:
        assert load_neural_inference(session,sid,plan_version=1) is None
        saved_model(session,sid,research_bars())
        with pytest.raises(ResearchNeuralError,match='older learning plan'):
            load_neural_inference(session,sid,plan_version=2)
        cp=session.scalar(select(ResearchNeuralEpoch))
        cp.weights_npz=b'unsafe'
        session.commit()
        with pytest.raises(ResearchNeuralError,match='checksum'):
            load_neural_inference(session,sid,plan_version=1)
    engine.dispose()


def test_neural_score_is_real_but_s4_guardian_never_approves(tmp_path):
    engine,factory=new_session_factory('sqlite:///'+str(tmp_path/'trace.db'))
    Base.metadata.create_all(engine)
    sid=student(factory)
    origin=datetime(2025,1,1,tzinfo=timezone.utc)
    rows=[]
    for i in range(1400):
        o=1800+i*.4
        rows.append({'open_time':(origin+timedelta(minutes=15*i)).isoformat(),
                     'open':str(o),'high':str(o+.9),'low':str(o-.5),'close':str(o+.4),
                     'volume':'1'})
    with factory() as session:
        context=saved_model(session,sid,rows)
        portion=rows[1130:1251]
        payload=TraceBatchInput.model_validate({
            'student_id':sid,'candles':[{
                'open_time':x['open_time'],'open':x['open'],'high':x['high'],
                'low':x['low'],'close':x['close']} for x in portion],
            'first_index':120,'last_index':120})
        report=inspect_trace_batch(payload,permitted_skills={'trend'},neural_context=context)
        row=report['observations'][0]
        assert report['neural_checkpoint_inference_enabled'] is True
        assert row['candidate'] is not None
        assert row['neural']['status']=='INFERENCE_AVAILABLE'
        assert row['neural']['checkpoint_sha256']==context['weights_sha256']
        assert len(row['neural_trace_sha256'])==64
        assert row['decision']=='NO_TRADE'
        assert row['guardian']=='NOT_EVALUATED'
        assert row['scout_b']=='NOT_TRAINED_OR_BOUND'
        assert report['simulated_orders_created']==0
    engine.dispose()


def test_authenticated_neural_api_predict_rejects_untrained_or_other_student(tmp_path,monkeypatch):
    client,headers,factory,engine=_setup(tmp_path,monkeypatch)
    sid=student(factory)
    bars=research_bars()
    body={'student_id':sid,'market':'XAUUSD','tactic':'trend',
          'candles':[{k:b[k] for k in ('open_time','open','high','low','close')}
                     for b in bars[1196:1201]]}
    base='/v1/students/'+sid+'/neural/predict'
    assert client.post(base,json=body).status_code==403
    assert client.post(base,headers=headers,json=body).status_code==409
    with factory() as session:
        saved_model(session,sid,bars)
    ok=client.post(base,headers=headers,json=body)
    assert ok.status_code==200,ok.text
    j=ok.json()
    assert j['model']['status']=='INFERENCE_AVAILABLE'
    assert j['model']['checkpoint_sha256']
    assert j['decision']=='NO_TRADE'
    assert j['guardian']=='NOT_EVALUATED'
    assert j['paper_trading_enabled'] is False
    assert j['live_trading_enabled'] is False
    other={**body,'student_id':str(__import__('uuid').uuid4())}
    assert client.post(base,headers=headers,json=other).status_code==422
    future={**body, 'candles':[dict(b) for b in body['candles']]}
    future['candles'][-1]['open_time']='2099-01-01T00:00:00Z'
    assert client.post(base,headers=headers,json=future).status_code==422
    client.cookies.clear()
    assert client.post(base,headers=headers,json=body).status_code==401
    engine.dispose()


def test_gapful_training_snapshot_rejected_for_index_phase_safety():
    bars=research_bars()
    bars.pop(120)
    with pytest.raises(ResearchNeuralError,match='contiguous M15'):
        build_training_snapshot(bars,market='XAUUSD',tactic='trend',
                               source_sha256='a'*64,plan_version=1)
