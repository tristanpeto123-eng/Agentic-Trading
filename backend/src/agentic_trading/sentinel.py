"""Sprint 10 fail-closed Sentinel: evidence integrity checks and permanent safety latch.

The Sentinel does not override Guardian or self-authorise financial activity.
This module does not implement broker execution or automatically release locks.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from agentic_trading.academy import _digest
from agentic_trading.evolution import _verify_revision, EvolutionError
from agentic_trading.skills_memory import _safe_episode, MemoryError
from agentic_trading.historical_store import source_bytes
from agentic_trading.data_engine import DataQualityError
from agentic_trading.storage import (AcademyJob, HistoricalDataset, TradeExperience,
    TrainingRun, TrainingCheckpoint, ExamRun, StrategyRevision, PeerLesson, SafetyLatch)


class SentinelError(ValueError):
    pass


def safety_latch(session: Session) -> dict:
    row=session.get(SafetyLatch, 'global')
    return {'locked': True, 'reason': row.reason if row else 'default_deny_no_authorization',
            'paper_enabled': False, 'live_enabled': False, 'unlock_available': False}


def engage_stop(session: Session, actor_id: str, reason: str) -> dict:
    if not 3 <= len(reason.strip()) <= 200:
        raise SentinelError('reason must be 3-200 characters')
    row=session.get(SafetyLatch,'global')
    if row is None:
        row=SafetyLatch(id='global',reason=reason.strip(),actor_id=actor_id,locked_at=datetime.now(timezone.utc))
        session.add(row)
    else:
        row.reason=reason.strip()
        row.actor_id=actor_id
        row.locked_at=datetime.now(timezone.utc)
    session.commit()
    return safety_latch(session)


def scan_health(session: Session, *, data_root: Path, checkpoints_root: Path,
                now: datetime, max_records: int = 5000) -> dict:
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise SentinelError('scan timestamp must be UTC')
    if not 1 <= max_records <= 50_000:
        raise SentinelError('invalid bounded scan limit')
    findings=[]
    counts={}
    def read(model, category):
        rows=session.scalars(select(model).limit(max_records+1)).all()
        counts[category]=len(rows)
        if len(rows)>max_records:
            findings.append({'area':category,'severity':'block','reason':'scan_limit_exceeded'})
            return []
        return rows
    root=data_root.resolve()
    for dataset in read(HistoricalDataset,'datasets'):
        if dataset.state!='quarantined':
            findings.append({'area':'data','severity':'block','reason':'unsupported_verified_state'})
        try:
            source_bytes(session, dataset, root)
        except (DataQualityError, OSError, ValueError):
            findings.append({'area':'data','severity':'block','reason':'historical_artifact_integrity'})
    for episode in read(TradeExperience,'episodes'):
        try: _safe_episode(episode)
        except (MemoryError, ValueError):
            findings.append({'area':'memory','severity':'block','reason':'episode_integrity'})
    for job in read(AcademyJob,'jobs'):
        if job.idempotency_sha256!=_digest(job.spec):
            findings.append({'area':'academy','severity':'block','reason':'job_spec_changed'})
        if job.state=='leased':
            until=job.lease_until
            if until is None or until.replace(tzinfo=timezone.utc) < now:
                findings.append({'area':'academy','severity':'warning','reason':'expired_training_lease'})
        if job.state=='completed_research' and job.result.get('trading_permissions') is not False:
            findings.append({'area':'academy','severity':'block','reason':'research_job_claims_trading_permission'})
    for strategy in read(StrategyRevision,'strategies'):
        try:_verify_revision(strategy)
        except (EvolutionError,ValueError,TypeError):
            findings.append({'area':'strategy','severity':'block','reason':'dna_integrity'})
    for lesson in read(PeerLesson,'peer_lessons'):
        if _digest(lesson.payload)!=lesson.payload_sha256 or lesson.payload.get('mentor_qualified') is not False:
            findings.append({'area':'mentorship','severity':'block','reason':'lesson_evidence_unverified'})
    ckroot=checkpoints_root.resolve()
    for ckpt in read(TrainingCheckpoint,'checkpoints'):
        path=(ckroot/ckpt.relative_path).resolve()
        if not path.is_relative_to(ckroot):
            findings.append({'area':'checkpoint','severity':'block','reason':'path_escape'})
        elif not path.is_file():
            findings.append({'area':'checkpoint','severity':'block','reason':'checkpoint_missing'})
        elif sha256(path.read_bytes()).hexdigest()!=ckpt.artifact_sha256:
            findings.append({'area':'checkpoint','severity':'block','reason':'checkpoint_corrupt'})
    for exam in read(ExamRun,'exams'):
        if (exam.qualification!='unqualified' or exam.report.get('qualification')!='unqualified'
            or exam.report.get('paper_trading_allowed') is not False
            or exam.report.get('live_trading_allowed') is not False):
            findings.append({'area':'exam','severity':'block','reason':'unexpected_promotion_state'})
    status=('blocked' if any(f['severity']=='block' for f in findings)
            else 'attention' if findings else 'research_safe')
    # Research-safe means **not known broken**; source qualification/trading remain off.
    return {'status':status,'scanned_at':now.isoformat(),'findings':findings,'counts':counts,
            'safety':safety_latch(session),'research_data_verified':False,
            'paper_trading_enabled':False,'live_trading_enabled':False,
            'note':'Integrity scan, not independent dataset validation or approval to trade.'}
