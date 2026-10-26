"""S8 fail-closed autonomous research foundation."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from agentic_trading.academy import AcademyError, lesson_plan, schedule_research, claim_job, complete_job, run_one_research_job, student_jobs
from agentic_trading.storage import Base, Student, LearningPlan, AcademyJob, new_session_factory
from test_neural_training import create_fixture, BASE


def test_curriculum_and_blocked_job_idempotency(tmp_path):
    _, factory, sid = create_fixture(tmp_path, count=11)
    with factory() as session:
        plan = lesson_plan(session, sid)
        assert plan['mode']=='directed' and plan['market_targets']==['XAUUSD']
        first = schedule_research(session, sid, as_of=BASE+timedelta(days=33))
        second = schedule_research(session, sid, as_of=BASE+timedelta(days=33))
        assert first.id == second.id and first.state=='blocked_data'
        assert claim_job(session,'worker',now=BASE+timedelta(days=40)) is None
        assert student_jobs(session,sid)[0]['qualification']=='unqualified'
        with pytest.raises(AcademyError,match='outside'):
            schedule_research(session,sid,as_of=BASE+timedelta(days=33),market='BTCUSD')
        with pytest.raises(AcademyError,match='UTC'):
            schedule_research(session,sid,as_of=datetime(2025,1,1))


def test_fixture_queue_recovery_and_research_only_run(tmp_path):
    _,factory,sid=create_fixture(tmp_path)
    now=BASE+timedelta(days=34)
    with factory() as s:
        j=schedule_research(s,sid,as_of=BASE+timedelta(days=33),fixture_research=True)
        assert j.state=='queued'
        claimed=claim_job(s,'worker-a',now=now)
        assert claimed.id==j.id and claimed.state=='leased'
        assert claim_job(s,'worker-b',now=now) is None
        with pytest.raises(AcademyError,match='worker'):
            complete_job(s,j.id,worker_id='worker-b',now=now,outcome='completed_research',report={})
        assert claim_job(s,'worker-b',now=now+timedelta(minutes=11)).attempts==2
        summary=run_one_research_job(s,worker_id='worker-b',checkpoint_root=tmp_path/'weights',now=now+timedelta(minutes=12))
        # job already leased by worker-b, so next queue poll has no work
        assert summary is None
        complete_job(s,j.id,worker_id='worker-b',now=now+timedelta(minutes=12),
                     outcome='completed_research',report={'research_only':True})
        assert s.get(AcademyJob,j.id).state=='completed_research'
        assert claim_job(s,'worker-c',now=now+timedelta(minutes=14)) is None
        new=schedule_research(s,sid,as_of=BASE+timedelta(days=32),fixture_research=True)
        result=run_one_research_job(s,worker_id='worker-c',checkpoint_root=tmp_path/'weights',now=now+timedelta(minutes=15))
        assert result and result['research_only'] is True
        assert s.get(AcademyJob,new.id).state=='completed_research'


def test_retry_budget_and_tamper(tmp_path):
    _,factory,sid=create_fixture(tmp_path)
    t=BASE+timedelta(days=34)
    with factory() as s:
        j=schedule_research(s,sid,as_of=BASE+timedelta(days=33),fixture_research=True)
        for i in range(3):
            row=claim_job(s, f'worker-{i}',now=t+timedelta(minutes=11*i))
            assert row is not None
        assert claim_job(s,'worker-4',now=t+timedelta(minutes=34)) is None
        assert s.get(AcademyJob,j.id).state=='failed'
        row=s.get(AcademyJob,j.id); row.spec={**row.spec,'market':'BTCUSD'};s.commit()
        with pytest.raises(AcademyError,match='tampered'):
            student_jobs(s,sid)
