"""Sprint 11: evidence-driven paper pilot readiness; fail-closed, no trading.

An intent to run a bounded paper pilot is not permission or a running service.
No broker, paper order, paper account or live execution endpoint is present.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4
import json

from sqlalchemy import select
from sqlalchemy.orm import Session
from agentic_trading.storage import (Student, HistoricalDataset, ExamRun, PaperPilotRequest,
                                     SafetyLatch, AuditEvent, CEO)


class PaperReadinessError(ValueError):
    pass


def _digest(v: dict) -> str:
    return sha256(json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def evaluate_readiness(session: Session, *, student_id: str | None = None) -> dict:
    """Never trust user-provided source or qualification labels.

    Sprint 11 has no independent verification/Registrar implementation and cannot
    safely authorise forward-paper deployment even if database rows are forged.
    """
    blockers = []
    if student_id is not None and session.get(Student, student_id) is None:
        raise PaperReadinessError('unknown student')
    datasets=session.scalars(select(HistoricalDataset)).all()
    if not datasets:
        blockers.append('No historical XAUUSD dataset imported')
    # This codebase has no independent provider-rights certification system.
    blockers.append('Provider licence, source authenticity and ≥12-month coverage not independently attested')
    blockers.append('Sealed out-of-sample validation and repeatable independent examination incomplete')
    blockers.append('No authorised Registrar-qualified research model version')
    blockers.append('No broker-independent forward paper feed/order simulator integration')
    blockers.append('CEO paper activation not requested or signed for an exact immutable scope')
    blockers.append('Operational broker-like fill reconciliation and kill-switch recovery not approved')
    latch=session.get(SafetyLatch,'global')
    blockers.append('Trading safety latch remains engaged' if latch else 'Trading safety latch defaults to engaged')
    return {'student_id':student_id,'ready':False,'activation_allowed':False,
            'paper_trading_enabled':False,'live_trading_enabled':False,
            'research_qualified_count':0,'imported_datasets':len(datasets),
            'blockers':blockers,'next_action':'Verify legitimate XAUUSD source rights and independent exam evidence',
            'note':'Paper readiness gate only. No account, orders, fills, positions or capital deployed.'}


def request_paper_review(session: Session, *, ceo: CEO, student_id: str,
                         market: str, model_sha256: str, capital_usd: Decimal,
                         risk_fraction: Decimal) -> PaperPilotRequest:
    """Log CEO review REQUEST, not an activation or financial order."""
    if session.get(Student,student_id) is None:
        raise PaperReadinessError('student not found')
    if market not in ('XAUUSD','EURUSD','GBPUSD','US500','NAS100','BTCUSD'):
        raise PaperReadinessError('unsupported market')
    if len(model_sha256)!=64 or any(c not in '0123456789abcdef' for c in model_sha256):
        raise PaperReadinessError('invalid model fingerprint')
    if not (Decimal('100') <= capital_usd <= Decimal('1000000')):
        raise PaperReadinessError('paper capital outside bounded review scope')
    if not (Decimal('0') < risk_fraction <= Decimal('0.02')):
        raise PaperReadinessError('paper risk fraction outside ceiling')
    p={'schema':'paper_request.v1','ceo_id':ceo.id,'student_id':student_id,'market':market,
       'model_sha256':model_sha256,'virtual_capital_usd':str(capital_usd),
       'risk_fraction':str(risk_fraction),'status':'blocked_review_only',
       'authorises_trading':False}
    digest=_digest(p)
    previous=session.scalar(select(PaperPilotRequest).where(PaperPilotRequest.payload_sha256==digest))
    if previous is not None:
        return previous
    row=PaperPilotRequest(id=str(uuid4()),student_id=student_id,ceo_id=ceo.id,
                          payload=p,payload_sha256=digest,status='blocked_review_only',
                          created_at=datetime.now(timezone.utc))
    session.add(row)
    session.add(AuditEvent(actor_id=ceo.id,action='paper_pilot.review_requested',
                           subject_id=row.id,detail={'approval':False,'scope_sha256':digest}))
    session.commit()
    return row


def paper_requests(session: Session, student_id: str | None = None) -> list[dict]:
    query=select(PaperPilotRequest)
    if student_id is not None:
        query=query.where(PaperPilotRequest.student_id==student_id)
    out=[]
    for row in session.scalars(query.order_by(PaperPilotRequest.created_at.desc())).all():
        if row.payload_sha256 != _digest(row.payload) or row.status != 'blocked_review_only' or row.payload.get('authorises_trading') is not False:
            raise PaperReadinessError('paper review record integrity failure')
        out.append({'id':row.id,**row.payload})
    return out
