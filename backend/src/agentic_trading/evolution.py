"""Sprint 9: strategy genealogy, immutable candidate DNA and non-authoritative peer lessons.

No candidate is qualified, no model is silently swapped, and mentoring requires
future independently attested evidence. Never copy sealed holdout records.
"""
from __future__ import annotations
from hashlib import sha256
from uuid import uuid4
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentic_trading.storage import Student, LearningPlan, StrategyRevision, PeerLesson
from agentic_trading.skills_memory import CATALOG


class EvolutionError(ValueError):
    pass


def _digest(value: dict) -> str:
    return sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _current_plan(session: Session, student_id: str):
    if session.get(Student, student_id) is None:
        raise EvolutionError('student not found')
    row = session.scalar(select(LearningPlan).where(LearningPlan.student_id == student_id)
                         .order_by(LearningPlan.version.desc()))
    if row is None:
        raise EvolutionError('learning plan missing')
    return row


def add_candidate(session: Session, student_id: str, *, family: str, market: str,
                  tactic: str, model_sha256: str, config: dict,
                  parent_ids: tuple[str, ...] = ()) -> StrategyRevision:
    """Immutable research candidate with provable ancestry. Does not train or deploy.

    A caller cannot choose qualification, research champion or live deployment.
    """
    plan = _current_plan(session, student_id)
    if not (1 <= len(family) <= 60 and family.strip() == family and family.isascii()):
        raise EvolutionError('invalid strategy family')
    if market not in ('XAUUSD','EURUSD','GBPUSD','US500','NAS100','BTCUSD') or tactic not in ('trend','breakout','range','scalping','swing'):
        raise EvolutionError('unsupported market or tactic')
    if plan.mode == 'directed' and (market not in plan.markets or tactic not in plan.skills):
        raise EvolutionError('candidate outside CEO research direction')
    if len(model_sha256) != 64 or any(ch not in '0123456789abcdef' for ch in model_sha256):
        raise EvolutionError('invalid model checksum')
    if len(parent_ids) > 2 or len(parent_ids) != len(set(parent_ids)):
        raise EvolutionError('invalid ancestry; at most two unique parents')
    if not isinstance(config, dict) or len(json.dumps(config, default=str)) > 8_000:
        raise EvolutionError('invalid or oversized strategy configuration')
    try:
        normalized = json.loads(json.dumps(config, sort_keys=True, allow_nan=False))
    except (ValueError, TypeError) as exc:
        raise EvolutionError('unserializable or nonfinite strategy parameters') from exc
    previous = session.scalars(select(StrategyRevision).where(
        StrategyRevision.student_id == student_id, StrategyRevision.family == family)
        .order_by(StrategyRevision.version)).all()
    existing = {x.id: x for x in previous}
    if any(pid not in existing for pid in parent_ids):
        raise EvolutionError('parent not in the same student family')
    for pid in parent_ids:
        if existing[pid].market != market or existing[pid].tactic != tactic:
            raise EvolutionError('incompatible parent strategy market or tactic')
        _verify_revision(existing[pid])
    version = max((r.version for r in previous), default=0) + 1
    payload = {'schema':'strategy_dna.v1', 'student_id':student_id, 'family':family,
               'version':version,'market':market,'tactic':tactic,'model_sha256':model_sha256,
               'configuration':normalized,'parent_ids':list(parent_ids),
               'research_plan_version':plan.version,'status':'research_candidate'}
    row = StrategyRevision(id=str(uuid4()), student_id=student_id, family=family,
                           version=version, market=market, tactic=tactic,
                           parent_ids=list(parent_ids), payload=payload,
                           payload_sha256=_digest(payload), state='research_candidate')
    session.add(row)
    session.commit()
    return row


def _verify_revision(row: StrategyRevision) -> dict:
    p = row.payload
    if (row.payload_sha256 != _digest(p) or row.student_id != p.get('student_id')
        or row.market != p.get('market') or row.tactic != p.get('tactic')
        or row.family != p.get('family') or row.version != p.get('version')
        or row.parent_ids != p.get('parent_ids') or row.state != 'research_candidate'
        or p.get('status') != 'research_candidate'):
        raise EvolutionError('Strategy DNA integrity failure')
    return p


def student_evolution(session: Session, student_id: str) -> dict:
    _current_plan(session, student_id)
    rows = session.scalars(select(StrategyRevision).where(StrategyRevision.student_id == student_id)
                           .order_by(StrategyRevision.family, StrategyRevision.version)).all()
    ids = {r.id for r in rows}
    items = []
    for row in rows:
        p = _verify_revision(row)
        if any(parent not in ids for parent in row.parent_ids):
            raise EvolutionError('Strategy DNA genealogy broken')
        items.append({'id':row.id, 'dna_sha256':row.payload_sha256, **p,
                      'qualified':False,'trading_permissions':False})
    return {'student_id':student_id, 'strategies':items,
            'note':'Research candidates only; no qualification or live model switching.'}


def share_lesson(session: Session, *, source_id: str, target_id: str,
                 candidate_id: str, skill_id: str) -> PeerLesson:
    """Record limited research lesson reference, never transfer scores/weights/holdout."""
    if source_id == target_id:
        raise EvolutionError('cannot self-mentor')
    _current_plan(session, source_id)
    plan = _current_plan(session, target_id)
    candidate = session.get(StrategyRevision, candidate_id)
    if candidate is None or candidate.student_id != source_id:
        raise EvolutionError('candidate does not belong to teacher')
    p = _verify_revision(candidate)
    if skill_id not in CATALOG:
        raise EvolutionError('skill is not in immutable curriculum catalog')
    # CATALOG is keyed by `market:XAUUSD`, `tactic:trend`, etc. For directed students
    # restrict what they are taught instead of silently expanding CEO scope.
    if plan.mode == 'directed':
        if skill_id.startswith('market:') and skill_id.split(':',1)[1] not in plan.markets:
            raise EvolutionError('peer lesson outside CEO market direction')
        if skill_id.startswith('tactic:') and skill_id.split(':',1)[1] not in plan.skills:
            raise EvolutionError('peer lesson outside CEO tactic direction')
    if skill_id.startswith('market:') and skill_id != 'market:'+p['market']:
        raise EvolutionError('lesson not supported by source candidate')
    if skill_id.startswith('tactic:') and skill_id != 'tactic:'+p['tactic']:
        raise EvolutionError('lesson not supported by source candidate')
    payload={'schema':'peer_lesson.v1','source_student_id':source_id,'target_student_id':target_id,
             'strategy_dna_sha256':candidate.payload_sha256,'candidate_id':candidate_id,
             'skill_id':skill_id,'target_plan_version':plan.version,
             'evidence':'unqualified_research_candidate','mentor_qualified':False,
             'teaching_status':'research_material_only'}
    hash_ = _digest(payload)
    previous = session.scalar(select(PeerLesson).where(PeerLesson.payload_sha256 == hash_))
    if previous is not None:
        return previous
    lesson=PeerLesson(id=str(uuid4()),source_student_id=source_id,target_student_id=target_id,
                      payload=payload,payload_sha256=hash_)
    session.add(lesson);session.commit()
    return lesson


def peer_lessons(session: Session, student_id: str) -> list[dict]:
    _current_plan(session, student_id)
    out=[]
    for row in session.scalars(select(PeerLesson).where(PeerLesson.target_student_id == student_id)).all():
        if row.payload_sha256 != _digest(row.payload) or row.payload['target_student_id'] != student_id:
            raise EvolutionError('peer lesson integrity failure')
        parent=session.get(StrategyRevision, row.payload['candidate_id'])
        if not parent or _verify_revision(parent) is None or parent.payload_sha256 != row.payload['strategy_dna_sha256']:
            raise EvolutionError('shared lesson source DNA changed')
        out.append({'id':row.id,**row.payload})
    return out


def mentorship_eligibility(session: Session, student_id: str, skill_id: str) -> dict:
    _current_plan(session, student_id)
    if skill_id not in CATALOG:
        raise EvolutionError('unknown skill')
    # A verified Examiner and promotion pipeline has not yet been enabled.
    return {'student_id':student_id,'skill_id':skill_id,'eligible':False,
            'blocker':'No independent source-verified qualification or reproducible competency evidence yet',
            'teaching_mode':'unqualified_research_peer_lessons_only'}
