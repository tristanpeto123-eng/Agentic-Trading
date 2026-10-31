"""Trusted-worker five-batch research checkpoint with immutable DB history.

This creates *unapplied* proposals from verified S5 closed TRAIN memories.
It cannot promote a model, train against holdout, modify catalog/other students,
enable an order route, or select an incumbent without independent validation.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentic_trading.five_batch_policy import (
    ClosedBatch, ClosedTrade, PolicyResearchError, propose_five_batch_policy,
)
from agentic_trading.skills_memory import CATALOG, _safe_episode, catalog_manifest, MemoryError
from agentic_trading.storage import Student, LearningPlan, TradeExperience, ResearchPolicyCandidate


def _digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _verify(row: ResearchPolicyCandidate) -> dict:
    payload = row.payload
    expected = {k: v for k, v in payload.items() if k != "candidate_sha256"}
    if (
        row.candidate_sha256 != payload.get("candidate_sha256")
        or _digest(expected) != row.candidate_sha256
        or row.student_id != payload.get("student_id")
        or row.market != payload.get("market")
        or row.version != payload.get("candidate_version")
        or row.state != "awaiting_independent_validation"
        or payload.get("status") != "awaiting_independent_validation"
        or payload.get("research_only") is not True
        or payload.get("applied_to_student") is not False
        or payload.get("qualified") is not False
        or payload.get("paper_trading_enabled") is not False
        or payload.get("live_trading_enabled") is not False
    ):
        raise PolicyResearchError("research policy checkpoint integrity violation")
    return payload


def checkpoint_five_batches(
    session: Session, *, student_id: str, market: str,
    batches: tuple[ClosedBatch, ...], as_of: datetime,
) -> ResearchPolicyCandidate:
    """Trusted internal orchestrator, never exposed as a public API.

    The source-of-truth is the archived, checksum-checked S5 experience.
    Callers may provide batch boundaries, but cannot spoof episode P&L, status,
    timestamps, student ownership or independent market-evidence provenance.
    """
    student = session.get(Student, student_id)
    if student is None:
        raise PolicyResearchError("student not found")
    plan = session.scalar(select(LearningPlan).where(LearningPlan.student_id == student_id)
                          .order_by(LearningPlan.version.desc()))
    if plan is None:
        raise PolicyResearchError("learning plan missing")
    if market not in ("XAUUSD", "EURUSD", "GBPUSD", "US500", "NAS100", "BTCUSD"):
        raise PolicyResearchError("unsupported market")
    if plan.mode == "directed" and market not in plan.markets:
        raise PolicyResearchError("market outside CEO learning direction")

    approved_tactics = ("trend", "breakout", "range", "scalping", "swing")
    if plan.mode == "directed":
        approved_tactics = tuple(t for t in approved_tactics if t in plan.skills)
    allowed = tuple("tactic:" + t for t in approved_tactics if "tactic:" + t in CATALOG)
    if not allowed:
        raise PolicyResearchError("student has no approved selection skills")
    if len(batches) != 5 or any(not 1 <= len(batch.trades) <= 100 for batch in batches):
        raise PolicyResearchError("exactly five nonempty bounded batches required")
    safe_batches = []
    for batch in batches:
        safe_trades = []
        for trade in batch.trades:
            row = session.get(TradeExperience, trade.trade_id)
            if row is None:
                raise PolicyResearchError("unknown archived trade ID")
            try:
                episode = _safe_episode(row)
            except MemoryError as exc:
                raise PolicyResearchError("trade memory integrity violation") from exc
            tactics = tuple(s for s in episode.skill_ids if s.startswith("tactic:"))
            if (
                str(episode.student_id) != student_id or episode.instrument != market
                or episode.partition.value != "train" or len(tactics) != 1
                or tactics[0] not in allowed
                or trade.skill_id != tactics[0] or trade.partition != "train"
                or trade.origin != episode.origin.value
                or trade.net_r != episode.net_r
                or trade.closed_at != episode.closed_at
                or trade.available_at != episode.available_at
            ):
                raise PolicyResearchError("episode conflicts with archived student TRAIN evidence")
            safe_trades.append(
                ClosedTrade(
                    trade_id=row.id, skill_id=tactics[0], net_r=episode.net_r,
                    closed_at=episode.closed_at, available_at=episode.available_at,
                    partition=episode.partition.value, origin=episode.origin.value,
                )
            )
        safe_batches.append(ClosedBatch(
            batch_id=batch.batch_id, student_id=batch.student_id,
            market=batch.market, completed_at=batch.completed_at, trades=tuple(safe_trades),
        ))

    manifest = catalog_manifest()
    # For now the active research baseline is fixed, never silently overwritten
    # with a candidate that has not completed independent validation.
    proposal = propose_five_batch_policy(
        student_id=student_id, market=market, as_of=as_of,
        skill_catalog_sha256=manifest["catalog_sha256"],
        allowed_skills=allowed,
        incumbent_scores={skill: Decimal("0.5") for skill in allowed},
        incumbent_version=1, batches=tuple(safe_batches),
    )
    existing = session.scalar(select(ResearchPolicyCandidate).where(
        ResearchPolicyCandidate.student_id == student_id,
        ResearchPolicyCandidate.market == market,
        ResearchPolicyCandidate.version == proposal["candidate_version"],
    ))
    if existing:
        _verify(existing)
        if existing.candidate_sha256 != proposal["candidate_sha256"]:
            raise PolicyResearchError("candidate version collision; validation needed before another update")
        return existing
    record = ResearchPolicyCandidate(
        id=str(uuid4()), student_id=student_id, market=market,
        version=proposal["candidate_version"], candidate_sha256=proposal["candidate_sha256"],
        payload=proposal, state="awaiting_independent_validation",
    )
    session.add(record)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise PolicyResearchError("concurrent policy checkpoint conflict") from exc
    return record


def research_policy_history(session: Session, student_id: str, *, market: str | None = None) -> list[dict]:
    if session.get(Student, student_id) is None:
        raise PolicyResearchError("student not found")
    query = select(ResearchPolicyCandidate).where(ResearchPolicyCandidate.student_id == student_id)
    if market is not None:
        query = query.where(ResearchPolicyCandidate.market == market)
    rows = session.scalars(query.order_by(ResearchPolicyCandidate.version)).all()
    return [_verify(row) for row in rows]
