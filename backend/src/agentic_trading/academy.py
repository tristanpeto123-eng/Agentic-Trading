"""Sprint 8 research Academy: deterministic lesson plans and durable, bounded job queue.

This module NEVER grants qualification, opens paper/live orders, or treats fixture data
as verified. Worker execution is explicitly a research-only offline operation.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4
import json

from sqlalchemy import select, update, or_, and_
from sqlalchemy.orm import Session

from agentic_trading.neural_training import TrainingSpec, TrainingError, train_student
from agentic_trading.skills_memory import catalog_manifest, _safe_episode, MemoryError
from agentic_trading.storage import AcademyJob, Student, LearningPlan, TradeExperience


class AcademyError(ValueError):
    pass


def _digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise AcademyError('time must be timezone-aware UTC')
    return value


def lesson_plan(session: Session, student_id: str) -> dict:
    """Derive curriculum without reading sealed holdout or other students' memories."""
    student = session.get(Student, student_id)
    if student is None:
        raise AcademyError('student does not exist')
    last = session.scalar(select(LearningPlan).where(LearningPlan.student_id == student_id)
                          .order_by(LearningPlan.version.desc()))
    if last is None:
        raise AcademyError('student has no learning plan')
    # Stable transparent curriculum; future intelligent selector must be separately validated.
    markets = list(last.markets) if last.mode == 'directed' else ['XAUUSD']
    tactics = [s for s in last.skills if s in ('trend', 'breakout', 'range', 'scalping', 'swing')] if last.mode == 'directed' else ['trend', 'range', 'breakout']
    catalog = catalog_manifest()
    return {'student_id': student_id, 'plan_version': last.version, 'mode': last.mode,
            'market_targets': markets, 'tactic_targets': tactics,
            'catalog_sha256': catalog['catalog_sha256'], 'teaching_enabled': bool(markets and tactics),
            'next_lesson': f'{markets[0]} {tactics[0]} basics' if markets and tactics else 'Await CEO research direction',
            'note': 'Deterministic curriculum proposal; neither mastery nor autonomous trading authority.'}


def _eligible_episodes(session: Session, student_id: str, market: str, tactic: str, as_of: datetime) -> int:
    rows = session.scalars(select(TradeExperience).where(TradeExperience.student_id == student_id,
                   TradeExperience.partition == 'train', TradeExperience.instrument == market,
                   TradeExperience.available_at <= as_of)).all()
    count = 0
    for row in rows:
        try:
            episode = _safe_episode(row)
        except MemoryError as exc:
            raise AcademyError(f'memory integrity check: {exc}') from exc
        if f'tactic:{tactic}' in episode.skill_ids:
            count += 1
    return count


def schedule_research(session: Session, student_id: str, *, as_of: datetime,
                      market: str | None = None, tactic: str | None = None,
                      fixture_research: bool = False) -> AcademyJob:
    """Schedule research ONLY; idempotent for plan+data window+lesson+mode.

    In the absence of verified data, jobs remain blocked unless an explicit trusted
    offline test enables fixture_research. This flag does NOT confer evidence rights.
    """
    as_of = _timestamp(as_of)
    plan = lesson_plan(session, student_id)
    market = market or next(iter(plan['market_targets']), None)
    tactic = tactic or next(iter(plan['tactic_targets']), None)
    if market not in plan['market_targets'] or tactic not in plan['tactic_targets']:
        raise AcademyError('lesson outside current CEO learning plan')
    examples = _eligible_episodes(session, student_id, market, tactic, as_of)
    job_spec = {'student_id': student_id, 'plan_version': plan['plan_version'], 'market': market,
                'tactic': tactic, 'as_of': as_of.isoformat(), 'fixture_research': fixture_research,
                'catalog_sha256': plan['catalog_sha256']}
    digest = _digest(job_spec)
    existing = session.scalar(select(AcademyJob).where(AcademyJob.idempotency_sha256 == digest))
    if existing:
        if existing.spec != job_spec:
            raise AcademyError('idempotency collision')
        return existing
    status = 'queued' if fixture_research and examples >= 12 else 'blocked_data'
    record = AcademyJob(id=str(uuid4()), student_id=student_id, plan_version=plan['plan_version'],
                        idempotency_sha256=digest, spec=job_spec, state=status, attempts=0,
                        result={'available_train_episodes': examples,
                                'blocker': None if status == 'queued' else 'No verified provider/rights and qualified partition available'},
                        created_at=datetime.now(timezone.utc))
    session.add(record)
    session.commit()
    return record


def claim_job(session: Session, worker_id: str, *, now: datetime, lease_minutes: int = 10) -> AcademyJob | None:
    """CAS lease: safe against two schedulers acquiring the same job.

    Expired leases may be reclaimed only up to 3 attempts. One job per poll.
    """
    _timestamp(now)
    if not (1 <= len(worker_id) <= 100 and 1 <= lease_minutes <= 60):
        raise AcademyError('invalid worker identity or lease')
    candidates = session.scalars(select(AcademyJob).where(
        or_(AcademyJob.state == 'queued',
            and_(AcademyJob.state == 'leased', AcademyJob.lease_until <= now)))
        .order_by(AcademyJob.created_at, AcademyJob.id)).all()
    for row in candidates:
        if row.attempts >= 3:
            session.execute(update(AcademyJob).where(AcademyJob.id == row.id).values(state='failed',
                         result={'error': 'retry budget exhausted'}))
            session.commit()
            continue
        # Single conditional update is atomic in both SQLite and PostgreSQL.
        changed = session.execute(update(AcademyJob).where(AcademyJob.id == row.id,
                AcademyJob.state == row.state, AcademyJob.attempts == row.attempts,
                or_(AcademyJob.state == 'queued', AcademyJob.lease_until <= now))
            .values(state='leased', attempts=row.attempts + 1, worker_id=worker_id,
                    lease_until=now + timedelta(minutes=lease_minutes)))
        session.commit()
        if changed.rowcount == 1:
            return session.get(AcademyJob, row.id)
    return None


def complete_job(session: Session, job_id: str, *, worker_id: str, now: datetime,
                 outcome: str, report: dict) -> AcademyJob:
    _timestamp(now)
    if outcome not in ('completed_research', 'failed'):
        raise AcademyError('invalid research-only completion state')
    row = session.get(AcademyJob, job_id)
    if row is None or row.state != 'leased' or row.worker_id != worker_id:
        raise AcademyError('no active lease for this worker')
    if not row.lease_until or now > row.lease_until.replace(tzinfo=timezone.utc):
        raise AcademyError('lease expired; report rejected')
    row.state = outcome
    row.worker_id = None
    row.lease_until = None
    row.result = {'report_sha256': _digest(report), 'report': report,
                  'qualification': 'unqualified', 'trading_permissions': False}
    session.commit()
    return row


def run_one_research_job(session: Session, *, worker_id: str, checkpoint_root: Path,
                         now: datetime) -> dict | None:
    """Offline bounded worker; research fixtures only, requires pre-populated TRAIN data.

    Does NOT schedule real data access, exams, registrar promotion or broker activity.
    """
    job = claim_job(session, worker_id, now=now)
    if job is None:
        return None
    params = job.spec
    try:
        if not params['fixture_research']:
            raise AcademyError('verified production training is not enabled')
        s = TrainingSpec(run_id=UUID(job.id), student_id=UUID(job.student_id),
                         plan_version=job.plan_version, market=params['market'], tactic=params['tactic'],
                         as_of=datetime.fromisoformat(params['as_of']), epochs=3,
                         seed=123, learning_rate=.03, allow_synthetic_research=True)
        result = train_student(session, s, checkpoint_root=checkpoint_root)
        # Safe bounded summary; never credentials or weights.
        summary = {'training_run_id': str(s.run_id), 'epochs': result['epoch'],
                   'snapshot_sha256': result['snapshot_sha256'], 'research_only': True}
        complete_job(session, job.id, worker_id=worker_id, now=now, outcome='completed_research', report=summary)
        return summary
    except (TrainingError, AcademyError, ValueError, OSError) as exc:
        complete_job(session, job.id, worker_id=worker_id, now=now, outcome='failed',
                     report={'error': type(exc).__name__, 'reason': str(exc)[:160]})
        return {'job_id': job.id, 'error': type(exc).__name__}


def student_jobs(session: Session, student_id: str) -> list[dict]:
    out = []
    for row in session.scalars(select(AcademyJob).where(AcademyJob.student_id == student_id)
                               .order_by(AcademyJob.created_at.desc(), AcademyJob.id.desc())).all():
        if row.idempotency_sha256 != _digest(row.spec):
            raise AcademyError('academy job spec tampered')
        out.append({'id': row.id, 'plan_version': row.plan_version, 'state': row.state,
                    'market': row.spec['market'], 'tactic': row.spec['tactic'], 'attempts': row.attempts,
                    'result': row.result, 'qualification': 'unqualified'})
    return out
