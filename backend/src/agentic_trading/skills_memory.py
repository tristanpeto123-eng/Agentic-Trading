"""Sprint 5: versioned curricula, immutable closed-trade episodes, and time-safe recall.

Only internal researchers may append experiences. No CEO API writes, training workers,
model weights, paper execution or qualification decisions are exposed by this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from pydantic import Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentic_trading.contracts.common import FrozenModel, Sha256, require_utc
from agentic_trading.storage import Student, HistoricalDataset, TradeExperience


class MemoryError(ValueError):
    """Invalid episode, inconsistency or attempted provenance/evaluation leakage."""


class Origin(StrEnum):
    SYNTHETIC_FIXTURE = 'synthetic_fixture'
    HISTORICAL_QUARANTINED = 'historical_quarantined'


class Outcome(StrEnum):
    GOOD = 'good'
    BAD = 'bad'
    FLAT = 'flat'


class ExamPartition(StrEnum):
    TRAIN = 'train'
    VALIDATION = 'validation'
    HOLDOUT = 'holdout'


class SkillSpec(FrozenModel):
    id: str
    version: int = Field(ge=1)
    title: str
    category: Literal['market', 'tactic', 'risk']
    prerequisite_ids: tuple[str, ...] = ()
    status: Literal['catalogued'] = 'catalogued'
    # Merely being in a curriculum never grants any mastery.


_CATALOG = (
    SkillSpec(id='market:XAUUSD', version=1, title='Gold (XAUUSD)', category='market'),
    SkillSpec(id='market:EURUSD', version=1, title='EUR/USD', category='market'),
    SkillSpec(id='market:GBPUSD', version=1, title='GBP/USD', category='market'),
    SkillSpec(id='market:US500', version=1, title='S&P 500 index', category='market'),
    SkillSpec(id='market:NAS100', version=1, title='Nasdaq 100 index', category='market'),
    SkillSpec(id='market:BTCUSD', version=1, title='Bitcoin (BTCUSD)', category='market'),
    SkillSpec(id='risk:risk_management', version=1, title='Risk management', category='risk'),
    SkillSpec(id='tactic:trend', version=1, title='Trend trading', category='tactic', prerequisite_ids=('risk:risk_management',)),
    SkillSpec(id='tactic:breakout', version=1, title='Breakout trading', category='tactic', prerequisite_ids=('risk:risk_management',)),
    SkillSpec(id='tactic:range', version=1, title='Range trading', category='tactic', prerequisite_ids=('risk:risk_management',)),
    SkillSpec(id='tactic:scalping', version=1, title='Scalping', category='tactic', prerequisite_ids=('risk:risk_management',)),
    SkillSpec(id='tactic:swing', version=1, title='Swing trading', category='tactic', prerequisite_ids=('risk:risk_management',)),
)
CATALOG: dict[str, SkillSpec] = {entry.id: entry for entry in _CATALOG}
assert len(CATALOG) == len(_CATALOG)
assert all(dep in CATALOG for s in _CATALOG for dep in s.prerequisite_ids)


def _sha(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')).hexdigest()


def catalog_manifest() -> dict:
    rows = [spec.model_dump(mode='json') for spec in _CATALOG]
    return {'schema_version': 'skill_catalog.v1', 'catalog_sha256': _sha({'skills': rows}), 'skills': rows,
            'note': 'Curriculum entries, not evidence of earned mastery.'}


class ClosedTradeEpisode(FrozenModel):
    """One frozen, post-close research result; derived outcomes cannot be self-labelled."""
    schema_version: Literal['closed_trade_memory.v1'] = 'closed_trade_memory.v1'
    event_id: UUID
    student_id: UUID
    source_id: str = Field(min_length=1, max_length=120)
    source_sha256: Sha256
    origin: Origin
    partition: ExamPartition
    instrument: Literal['XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'BTCUSD']
    strategy_version: str = Field(min_length=1, max_length=100)
    proposal_sha256: Sha256
    skill_ids: tuple[str, ...] = Field(min_length=2, max_length=12)
    signal_at: datetime
    opened_at: datetime
    closed_at: datetime
    available_at: datetime
    initial_risk_usd: Decimal = Field(gt=0)
    gross_pnl_usd: Decimal
    spread_cost_usd: Decimal = Field(ge=0)
    slippage_cost_usd: Decimal = Field(ge=0)
    fees_usd: Decimal = Field(ge=0)
    mfe_r: Decimal = Field(ge=0)
    mae_r: Decimal = Field(ge=0)
    close_reason: str = Field(min_length=1, max_length=100)
    # Time-aware contextual retrieval only; this is NOT a market regime prediction.
    market_regime: Literal['TREND_UP', 'TREND_DOWN', 'RANGE', 'CHOP', 'UNCERTAIN']

    @field_validator('signal_at', 'opened_at', 'closed_at', 'available_at')
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode='after')
    def enforce_integrity(self):
        if not (self.signal_at <= self.opened_at < self.closed_at <= self.available_at):
            raise ValueError('episode must become available after its trade is closed')
        if self.instrument not in {k.removeprefix('market:') for k in self.skill_ids if k.startswith('market:')}:
            raise ValueError('episode must reference its own market skill')
        if len(set(self.skill_ids)) != len(self.skill_ids) or any(k not in CATALOG for k in self.skill_ids):
            raise ValueError('skill references must be unique and catalogued')
        if not any(k.startswith('tactic:') for k in self.skill_ids):
            raise ValueError('episode must reference an actual trading tactic skill')
        for skill in self.skill_ids:
            if any(dep not in self.skill_ids for dep in CATALOG[skill].prerequisite_ids):
                raise ValueError('episode missing skill prerequisite')
        if not all(x.is_finite() for x in (
            self.initial_risk_usd, self.gross_pnl_usd, self.spread_cost_usd,
            self.slippage_cost_usd, self.fees_usd, self.mfe_r, self.mae_r,
        )):
            raise ValueError('episode financial values must be finite')
        return self

    @property
    def net_pnl_usd(self) -> Decimal:
        return self.gross_pnl_usd - self.spread_cost_usd - self.slippage_cost_usd - self.fees_usd

    @property
    def net_r(self) -> Decimal:
        return self.net_pnl_usd / self.initial_risk_usd

    @property
    def outcome(self) -> Outcome:
        return Outcome.GOOD if self.net_pnl_usd > 0 else Outcome.BAD if self.net_pnl_usd < 0 else Outcome.FLAT

    @property
    def content_sha256(self) -> str:
        return _sha(self.model_dump(mode='json'))


def append_episode(session: Session, episode: ClosedTradeEpisode) -> TradeExperience:
    """Append-only, idempotent on exact content; reject conflicting event ID and spoofed data.

    The caller is a trusted internal research orchestrator, NEVER an arbitrary API user.
    Only synthetic fixtures and known quarantined datasets are admissible in Sprint 5.
    Examination partitions may be archived but are NEVER recalled into training.
    """
    student = session.get(Student, str(episode.student_id))
    if student is None:
        raise MemoryError('unknown student')
    if episode.origin == Origin.HISTORICAL_QUARANTINED:
        dataset = session.get(HistoricalDataset, episode.source_id)
        if dataset is None or dataset.source_hash != episode.source_sha256 or dataset.state != 'quarantined':
            raise MemoryError('historical provenance does not match a quarantined dataset')
        if dataset.source_manifest.get('instrument') != episode.instrument:
            raise MemoryError('instrument provenance mismatch')
    elif not episode.source_id.startswith('fixture:'):
        raise MemoryError('synthetic episodes must identify their fixture')
    existing = session.get(TradeExperience, str(episode.event_id))
    if existing:
        if existing.payload_hash != episode.content_sha256:
            raise MemoryError('event ID collision or attempted episode overwrite')
        return existing
    row = TradeExperience(
        id=str(episode.event_id), student_id=str(episode.student_id),
        payload_hash=episode.content_sha256,
        payload=episode.model_dump(mode='json'),
        source_id=episode.source_id, source_sha256=episode.source_sha256,
        origin=episode.origin.value, partition=episode.partition.value,
        instrument=episode.instrument, strategy_version=episode.strategy_version,
        skill_ids=list(episode.skill_ids),
        available_at=episode.available_at, closed_at=episode.closed_at,
        outcome=episode.outcome.value, net_pnl_usd=str(episode.net_pnl_usd),
        net_r=str(episode.net_r),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise MemoryError('episode collision; retry after re-reading event') from exc
    return row


def _safe_episode(row: TradeExperience) -> ClosedTradeEpisode:
    try:
        episode = ClosedTradeEpisode.model_validate(row.payload)
    except (ValidationError, TypeError, ValueError) as exc:
        raise MemoryError('archived episode payload invalid or tampered') from exc
    if (episode.content_sha256 != row.payload_hash or row.student_id != str(episode.student_id)
        or row.source_sha256 != episode.source_sha256 or row.source_id != episode.source_id
        or row.origin != episode.origin.value or row.partition != episode.partition.value
        or row.instrument != episode.instrument or row.strategy_version != episode.strategy_version
        or row.skill_ids != list(episode.skill_ids)
        or row.net_pnl_usd != str(episode.net_pnl_usd) or row.net_r != str(episode.net_r)
        or row.outcome != episode.outcome.value
        or (row.available_at.replace(tzinfo=timezone.utc) if row.available_at.tzinfo is None else row.available_at) != episode.available_at
        or (row.closed_at.replace(tzinfo=timezone.utc) if row.closed_at.tzinfo is None else row.closed_at) != episode.closed_at):
        raise MemoryError('archived episode integrity mismatch')
    return episode


def _format(row: TradeExperience) -> dict:
    e = _safe_episode(row)
    return {
        'event_id': str(e.event_id), 'student_id': str(e.student_id),
        'strategy_version': e.strategy_version, 'instrument': e.instrument, 'skill_ids': list(e.skill_ids),
        'origin': e.origin.value, 'partition': e.partition.value, 'source_sha256': e.source_sha256,
        'available_at': e.available_at.isoformat(), 'closed_at': e.closed_at.isoformat(),
        'outcome': e.outcome.value, 'net_pnl_usd': str(e.net_pnl_usd), 'net_r': str(e.net_r),
        'gross_pnl_usd': str(e.gross_pnl_usd), 'fees_usd': str(e.fees_usd),
        'spread_cost_usd': str(e.spread_cost_usd), 'slippage_cost_usd': str(e.slippage_cost_usd),
        'mfe_r': str(e.mfe_r), 'mae_r': str(e.mae_r), 'close_reason': e.close_reason,
        'market_regime': e.market_regime, 'content_sha256': e.content_sha256,
        'research_qualified': False,
    }


def read_student_memory(session: Session, student_id: str, *, limit: int = 100) -> list[dict]:
    rows = session.scalars(select(TradeExperience).where(TradeExperience.student_id == student_id)
                           .order_by(TradeExperience.available_at.desc(), TradeExperience.id.desc()).limit(limit)).all()
    return [_format(row) for row in rows]


def recall_training_examples(session: Session, student_id: str, *, as_of: datetime,
                             skill_ids: tuple[str, ...] = (), instrument: str | None = None,
                             market_regime: str | None = None, exclude_source_sha256: str | None = None,
                             limit: int = 20) -> list[dict]:
    """Point-in-time train-only retrieval: never include validation/holdout or future outcomes."""
    require_utc(as_of)
    if not (1 <= limit <= 100):
        raise MemoryError('recall limit must be 1..100')
    if any(skill not in CATALOG for skill in skill_ids):
        raise MemoryError('unknown recall skill')
    query = (select(TradeExperience)
             .where(TradeExperience.student_id == student_id,
                    TradeExperience.partition == ExamPartition.TRAIN.value,
                    TradeExperience.available_at <= as_of)
             .order_by(TradeExperience.available_at.desc(), TradeExperience.id.desc()))
    if instrument:
        query = query.where(TradeExperience.instrument == instrument)
    if exclude_source_sha256:
        query = query.where(TradeExperience.source_sha256 != exclude_source_sha256)
    matches: list[dict] = []
    for row in session.scalars(query).yield_per(100):
        episode = _safe_episode(row)
        if skill_ids and not all(skill in episode.skill_ids for skill in skill_ids):
            continue
        if market_regime and episode.market_regime != market_regime:
            continue
        matches.append(_format(row))
        if len(matches) >= limit:
            break
    return matches


def student_skill_progress(session: Session, student: Student) -> dict:
    """Observed archival P&L, not mastery. Only independent Examiner may confer mastery."""
    plans = sorted(student.plans, key=lambda p: p.version)
    latest = plans[-1]
    targets = [f'market:{m}' for m in latest.markets] + [f'tactic:{s}' if s != 'risk_management' else 'risk:risk_management' for s in latest.skills]
    rows = session.scalars(select(TradeExperience).where(TradeExperience.student_id == student.id)
                           .order_by(TradeExperience.available_at.asc(), TradeExperience.id.asc())).all()
    per_skill = {}
    # Validate every archived event, not merely those matching the current targets.
    for row in rows:
        _safe_episode(row)
    for key in set(targets).union(*(set(row.skill_ids) for row in rows)):
        skill = CATALOG.get(key)
        if skill is None:
            raise MemoryError('archived unknown skill reference')
        relevant = [row for row in rows if key in row.skill_ids]
        per_skill[key] = {
            'skill_id': key, 'title': skill.title, 'version': skill.version,
            'target': key in targets, 'experience_count': len(relevant),
            'good': sum(row.outcome == Outcome.GOOD for row in relevant),
            'bad': sum(row.outcome == Outcome.BAD for row in relevant),
            'flat': sum(row.outcome == Outcome.FLAT for row in relevant),
            'net_pnl_usd': str(sum((Decimal(row.net_pnl_usd) for row in relevant), Decimal('0'))),
            'net_r': str(sum((Decimal(row.net_r) for row in relevant), Decimal('0'))),
            'mastery_status': 'unassessed',
            'research_qualified': False,
            'evidence_warning': 'S5 archive is not independent examination evidence',
        }
    return {'student_id': student.id, 'catalog_sha256': catalog_manifest()['catalog_sha256'],
            'qualification': 'unqualified', 'skills': sorted(per_skill.values(), key=lambda x: x['skill_id'])}
