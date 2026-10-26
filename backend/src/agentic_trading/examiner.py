"""Sprint 7 independent historical *research* Examiner, offline and fail-closed.

Replays both candidates on the same frozen M1 quote stream and cost profile. Records
independently recomputed financial metrics, not trusted user-provided scores.

The available S2 source remains quarantined, S6 memories only synthetic/unverified.
For that reason this Examiner deliberately never grants research qualification,
changes a champion, or authorizes paper/live operation. A later independently
verified source + sealed holdout + Registrar can add a separate promotion path.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import UUID
import json

from pydantic import Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentic_trading.contracts.common import EvidenceKind, FrozenModel, Sha256, require_utc
from agentic_trading.neural_training import _jsonhash as training_hash, _safe_path
from agentic_trading.simulator import (
    HistoricalOrder, QuoteBar, ReplayCosts, ReplayError, ReplayReport, replay,
)
from agentic_trading.storage import (
    ExamRun, HistoricalDataset, Student, TrainingCheckpoint, TrainingRun,
)


class ExaminationError(ValueError):
    """Invalid, untrusted, tampered, or non-comparable historical examination."""


class ExamPlan(FrozenModel):
    schema_version: Literal['independent_exam_plan.v1'] = 'independent_exam_plan.v1'
    exam_id: UUID
    student_id: UUID
    training_run_id: UUID
    challenger_model_sha256: Sha256
    challenger_orders_sha256: Sha256
    incumbent_model_sha256: Sha256 | None = None
    incumbent_orders_sha256: Sha256 | None = None
    dataset_id: UUID
    source_sha256: Sha256
    market: Literal['XAUUSD'] = 'XAUUSD'
    tactic: Literal['trend', 'breakout', 'range', 'scalping', 'swing']
    train_cutoff: datetime
    holdout_start: datetime
    holdout_end: datetime
    embargo_minutes: int = Field(default=240, ge=240, le=10080)
    min_closed_trades: int = Field(default=100, ge=100)
    profit_factor_floor: Decimal = Field(default=Decimal('1.20'), ge=Decimal('1.20'))
    max_drawdown_ceiling: Decimal = Field(default=Decimal('0.15'), ge=0, le=Decimal('0.15'))

    @field_validator('train_cutoff', 'holdout_start', 'holdout_end')
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode='after')
    def inspect_boundaries(self):
        if not (self.train_cutoff + timedelta(minutes=self.embargo_minutes) <= self.holdout_start < self.holdout_end):
            raise ValueError('separate chronological holdout with embargo required')
        if (self.incumbent_model_sha256 is None) != (self.incumbent_orders_sha256 is None):
            raise ValueError('incumbent model and order snapshot must be supplied together')
        return self


class ExamMetrics(FrozenModel):
    closed_trades: int
    rejected_trades: int
    unresolved_trades: int
    wins: int
    losses: int
    flat: int
    net_pnl_usd: Decimal
    profit_factor: Decimal | None
    max_drawdown_fraction: Decimal
    final_equity_usd: Decimal
    journal_sha256: Sha256


class ExamVerdict(FrozenModel):
    schema_version: Literal['independent_exam_report.v1'] = 'independent_exam_report.v1'
    exam_id: UUID
    student_id: UUID
    market: str
    tactic: str
    challenger_model_sha256: Sha256
    incumbent_model_sha256: Sha256 | None
    plan_sha256: Sha256
    source_sha256: Sha256
    quote_stream_sha256: Sha256
    configuration_sha256: Sha256
    challenger: ExamMetrics
    incumbent: ExamMetrics
    challenger_outperformed: bool
    numerical_thresholds_passed: bool
    evidence_kind: EvidenceKind
    dataset_verification: Literal['quarantined', 'unverified']
    verdict: Literal['PROVISIONAL_NUMERIC_PASS', 'PROVISIONAL_NUMERIC_FAIL']
    qualification: Literal['unqualified'] = 'unqualified'
    research_promotion_allowed: Literal[False] = False
    paper_trading_allowed: Literal[False] = False
    live_trading_allowed: Literal[False] = False
    blockers: tuple[str, ...]
    report_sha256: Sha256


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, default=str).encode()).hexdigest()


def orders_digest(orders: tuple[HistoricalOrder, ...]) -> str:
    """Frozen tuple contents, including proposed model and Guardian decisions."""
    return _hash([x.model_dump(mode='json') for x in orders])


def _report_metrics(report: ReplayReport) -> ExamMetrics:
    closed = [r for r in report.trades if r.status == 'CLOSED']
    wins = sum(1 for r in closed if r.net_pnl_usd > 0)
    losses = sum(1 for r in closed if r.net_pnl_usd < 0)
    flat = len(closed) - wins - losses
    gained = sum((r.net_pnl_usd for r in closed if r.net_pnl_usd > 0), Decimal('0'))
    lost = -sum((r.net_pnl_usd for r in closed if r.net_pnl_usd < 0), Decimal('0'))
    pf = gained / lost if lost > 0 else None  # no losses: undefined, not infinite success
    return ExamMetrics(
        closed_trades=len(closed),
        rejected_trades=sum(r.status == 'REJECTED' for r in report.trades),
        unresolved_trades=sum(r.status == 'UNRESOLVED' for r in report.trades),
        wins=wins, losses=losses, flat=flat,
        net_pnl_usd=report.net_pnl_usd, profit_factor=pf,
        max_drawdown_fraction=report.max_drawdown_fraction,
        final_equity_usd=report.final_equity_usd,
        journal_sha256=report.journal_sha256,
    )


def _verify_training_source(session: Session, plan: ExamPlan, checkpoint_root: Path) -> None:
    run = session.get(TrainingRun, str(plan.training_run_id))
    if run is None or run.student_id != str(plan.student_id):
        raise ExaminationError('challenger training run missing or student mismatch')
    if run.state != 'research_only' or run.qualification != 'unqualified':
        raise ExaminationError('unexpected training run authority')
    if run.config_sha256 != training_hash(run.config) or run.snapshot_sha256 != training_hash(run.snapshot_manifest):
        raise ExaminationError('training metadata checksum mismatch')
    if run.config.get('market') != plan.market or run.config.get('tactic') != plan.tactic:
        raise ExaminationError('trained market or tactic mismatch')
    try:
        as_of = datetime.fromisoformat(run.config['as_of'])
        feature_examples = run.snapshot_manifest['examples']
        if any(require_utc(datetime.fromisoformat(ex['available_at'])) > plan.train_cutoff for ex in feature_examples):
            raise ExaminationError('training snapshot overlaps sealed holdout')
    except (ValueError, KeyError, TypeError) as exc:
        raise ExaminationError('training snapshot provenance malformed') from exc
    require_utc(as_of)
    if as_of > plan.train_cutoff:
        raise ExaminationError('training cutoff later than exam training boundary')
    if not set(run.snapshot_manifest.get('train_event_ids', [])).isdisjoint(
        run.snapshot_manifest.get('development_validation_event_ids', [])):
        raise ExaminationError('training/development event overlap')
    if set(run.snapshot_manifest.get('train_event_ids', []) + run.snapshot_manifest.get('development_validation_event_ids', [])) != {x.get('id') for x in feature_examples}:
        raise ExaminationError('training snapshot example index mismatch')
    for item in feature_examples:
        if require_utc(datetime.fromisoformat(item['available_at'])) > as_of:
            raise ExaminationError('snapshot contains future episode')
        if item.get('id') is None or item.get('hash') is None:
            raise ExaminationError('untraceable snapshot episode')
    rows = session.scalars(select(TrainingCheckpoint).where(TrainingCheckpoint.run_id == run.id)
                           .order_by(TrainingCheckpoint.epoch.desc())).all()
    if not rows or rows[0].epoch != run.config.get('epochs'):
        raise ExaminationError('challenger training incomplete')
    checkpoint = rows[0]
    if checkpoint.artifact_sha256 != plan.challenger_model_sha256 or checkpoint.snapshot_sha256 != run.snapshot_sha256:
        raise ExaminationError('challenger checkpoint hash or training snapshot mismatch')
    destination = _safe_path(checkpoint_root, checkpoint.relative_path)
    try:
        data = destination.read_bytes()
    except OSError as exc:
        raise ExaminationError('challenger checkpoint unavailable') from exc
    if sha256(data).hexdigest() != checkpoint.artifact_sha256:
        raise ExaminationError('challenger checkpoint artifact tampered')


def _verify_orders(plan: ExamPlan, orders: tuple[HistoricalOrder, ...], *, challenger: bool) -> None:
    expected = plan.challenger_orders_sha256 if challenger else plan.incumbent_orders_sha256
    if orders_digest(orders) != expected:
        raise ExaminationError('order snapshot changed since exam plan was frozen')
    if len(orders) > 5000:
        raise ExaminationError('exam contains too many orders')
    for instruction in orders:
        proposal = instruction.proposal
        if proposal.student_id != plan.student_id or proposal.instrument != plan.market:
            raise ExaminationError('proposal student or market mismatch')
        model = plan.challenger_model_sha256 if challenger else plan.incumbent_model_sha256
        if proposal.model_sha256 != model:
            raise ExaminationError('proposal model differs from frozen exam model')
        if proposal.tactic_id != plan.tactic:
            raise ExaminationError('proposal tactic differs from exam scope')
        if proposal.created_at < plan.holdout_start or proposal.expires_at > plan.holdout_end:
            raise ExaminationError('proposal outside sealed examination interval')
        if not (plan.holdout_start <= instruction.guardian.decided_at < plan.holdout_end):
            raise ExaminationError('Guardian decision outside examination interval')
    if tuple(sorted(orders, key=lambda x: (x.guardian.decided_at, str(x.proposal.proposal_id)))) != orders:
        raise ExaminationError('frozen proposals must be chronologically ordered')


def examine(
    session: Session, plan: ExamPlan, *, checkpoint_root: Path,
    bars: tuple[QuoteBar, ...], challenger_orders: tuple[HistoricalOrder, ...],
    incumbent_orders: tuple[HistoricalOrder, ...], costs: ReplayCosts,
) -> ExamVerdict:
    """Trusted offline worker; immutable results, no qualification or promotion side-effects."""
    if session.get(Student, str(plan.student_id)) is None:
        raise ExaminationError('student missing')
    dataset = session.get(HistoricalDataset, str(plan.dataset_id))
    if dataset is None or dataset.source_hash != plan.source_sha256:
        raise ExaminationError('dataset missing or source provenance mismatch')
    if dataset.source_manifest.get('instrument') != plan.market:
        raise ExaminationError('historical source market mismatch')
    if dataset.state != 'quarantined':
        raise ExaminationError('data state is not supported by Sprint 7; independent verification unavailable')
    if not bars or len(bars) > 250_000:
        raise ExaminationError('bounded nonempty M1 execution tape required')
    if bars[0].open_time < plan.holdout_start or bars[-1].open_time + timedelta(minutes=1) > plan.holdout_end:
        raise ExaminationError('quote tape extends beyond the sealed examination window')
    _verify_training_source(session, plan, checkpoint_root)
    _verify_orders(plan, challenger_orders, challenger=True)
    if plan.incumbent_model_sha256 is None:
        if incumbent_orders:
            raise ExaminationError('cash baseline cannot submit trade orders')
    else:
        _verify_orders(plan, incumbent_orders, challenger=False)
    for previous, current in zip(bars, bars[1:]):
        if current.open_time <= previous.open_time:
            raise ExaminationError('M1 tape is not strictly chronological')
    # Replay independently for both competitors, with identical M1 tape, costs and as-of.
    try:
        challenger = replay(bars=bars, orders=challenger_orders, costs=costs,
                            evidence_kind=EvidenceKind.HISTORICAL_UNVERIFIED,
                            source_sha256=plan.source_sha256, as_of=plan.holdout_end)
        incumbent = replay(bars=bars, orders=incumbent_orders, costs=costs,
                           evidence_kind=EvidenceKind.HISTORICAL_UNVERIFIED,
                           source_sha256=plan.source_sha256, as_of=plan.holdout_end)
    except ReplayError as exc:
        raise ExaminationError(f'historical replay failed closed: {exc}') from exc
    if challenger.quote_stream_sha256 != incumbent.quote_stream_sha256 or challenger.configuration_sha256 != incumbent.configuration_sha256:
        raise ExaminationError('candidate and incumbent comparison used different conditions')
    challenger_metrics = _report_metrics(challenger)
    incumbent_metrics = _report_metrics(incumbent)
    outperformed = challenger_metrics.net_pnl_usd > incumbent_metrics.net_pnl_usd
    passed = (
        challenger_metrics.closed_trades >= plan.min_closed_trades
        and challenger_metrics.profit_factor is not None
        and challenger_metrics.profit_factor >= plan.profit_factor_floor
        and challenger_metrics.max_drawdown_fraction <= plan.max_drawdown_ceiling
        and challenger_metrics.net_pnl_usd > 0
        and challenger_metrics.unresolved_trades == 0
        and outperformed
    )
    blockers = (
        'SOURCE_UNVERIFIED_OR_RIGHTS_NOT_APPROVED',
        'HOLDOUT_INDEPENDENCE_AND_MULTIPLE_TRIAL_SELECTION_NOT_CERTIFIED',
        'SECOND_INDEPENDENT_REPLAY_NOT_ATTESTED',
        'EXECUTION_QUOTES_NOT_BOUND_TO_VERIFIED_SOURCE_ARTIFACT',
        'STRATEGY_PROPOSALS_NOT_VERIFIED_AS_MODEL_GENERATED',
        'INCUMBENT_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED',
        'REGISTRAR_AND_LIVE_AUTHORIZATION_NOT_IMPLEMENTED',
    )
    record = {
        'exam_id': str(plan.exam_id), 'student_id': str(plan.student_id),
        'market': plan.market, 'tactic': plan.tactic,
        'challenger_model_sha256': plan.challenger_model_sha256,
        'incumbent_model_sha256': plan.incumbent_model_sha256,
        'plan_sha256': _hash(plan.model_dump(mode='json')),
        'source_sha256': plan.source_sha256,
        'quote_stream_sha256': challenger.quote_stream_sha256,
        'configuration_sha256': challenger.configuration_sha256,
        'challenger': challenger_metrics.model_dump(mode='json'),
        'incumbent': incumbent_metrics.model_dump(mode='json'),
        'challenger_outperformed': outperformed,
        'numerical_thresholds_passed': passed,
        'evidence_kind': EvidenceKind.HISTORICAL_UNVERIFIED,
        'dataset_verification': 'quarantined',
        'verdict': 'PROVISIONAL_NUMERIC_PASS' if passed else 'PROVISIONAL_NUMERIC_FAIL',
        'qualification': 'unqualified',
        'research_promotion_allowed': False, 'paper_trading_allowed': False,
        'live_trading_allowed': False,
        'blockers': blockers,
    }
    initial = ExamVerdict(**record, report_sha256='0' * 64)
    canonical = initial.model_dump(mode='json')
    verdict = initial.model_copy(update={'report_sha256': _hash({k: v for k, v in canonical.items() if k != 'report_sha256'})})
    previous = session.get(ExamRun, str(plan.exam_id))
    if previous:
        if previous.plan_sha256 != verdict.plan_sha256 or previous.report_sha256 != verdict.report_sha256:
            raise ExaminationError('exam ID reused with different evidence or results')
        if _hash({k: v for k, v in previous.report.items() if k != 'report_sha256'}) != previous.report_sha256 or previous.report != verdict.model_dump(mode='json'):
            raise ExaminationError('stored examination report tampered')
        return verdict
    session.add(ExamRun(
        id=str(plan.exam_id), student_id=str(plan.student_id),
        training_run_id=str(plan.training_run_id), plan_sha256=verdict.plan_sha256,
        report_sha256=verdict.report_sha256, report=verdict.model_dump(mode='json'),
        dataset_id=str(plan.dataset_id), source_sha256=plan.source_sha256,
        challenger_model_sha256=plan.challenger_model_sha256,
        market=plan.market, tactic=plan.tactic,
        verdict=verdict.verdict, qualification='unqualified',
    ))
    session.commit()
    return verdict


def student_exam_history(session: Session, student_id: str, *, limit: int = 20) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ExaminationError('limit must be 1..100')
    records = session.scalars(select(ExamRun).where(ExamRun.student_id == student_id)
                              .order_by(ExamRun.created_at.desc(), ExamRun.id.desc()).limit(limit)).all()
    result: list[dict] = []
    for row in records:
        if _hash({k: v for k, v in row.report.items() if k != 'report_sha256'}) != row.report_sha256 or row.report.get('plan_sha256') != row.plan_sha256:
            raise ExaminationError('exam report checksum mismatch')
        verdict = ExamVerdict.model_validate(row.report)
        if (str(verdict.exam_id) != row.id or str(verdict.student_id) != student_id
            or verdict.verdict != row.verdict or row.qualification != 'unqualified'
            or verdict.source_sha256 != row.source_sha256
            or verdict.challenger_model_sha256 != row.challenger_model_sha256):
            raise ExaminationError('exam metadata integrity mismatch')
        result.append(verdict.model_dump(mode='json'))
    return result
