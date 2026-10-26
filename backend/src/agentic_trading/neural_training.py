"""Sprint 6: reproducible, CPU-only supervised neural *research* training.

No broker, live/paper, automatic jobs or Examiner promotion exists here. This trainer
consumes only S5 closed trade episodes in TRAIN partition with known availability.
Holdout/independent validation partitions are never read, even for model evaluation.

Optional torch dependency is loaded only for actual training/checkpoint verification.
The checkpoint stores NumPy tensors with allow_pickle=False, never pickle or torch.load.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import UUID
import io
import json
import os
import tempfile

import numpy as np
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentic_trading.contracts.common import FrozenModel, require_utc
from agentic_trading.skills_memory import CATALOG, ExamPartition, Origin, MemoryError, _safe_episode, catalog_manifest
from agentic_trading.storage import Student, LearningPlan, TradeExperience, TrainingRun, TrainingCheckpoint

REGIMES = ('TREND_UP', 'TREND_DOWN', 'RANGE', 'CHOP', 'UNCERTAIN')
MARKETS = ('XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'BTCUSD')
TACTICS = ('trend', 'breakout', 'range', 'scalping', 'swing')
FEATURE_NAMES = tuple('regime:' + x for x in REGIMES) + tuple('market:' + x for x in MARKETS) + tuple('tactic:' + x for x in TACTICS)
FEATURE_SCHEMA = 's6.signal_context.v1'
ARCHITECTURE = 'mlp_16_16_2.v1'
MAX_CHECKPOINT_BYTES = 1_000_000


class TrainingError(ValueError):
    """Fail-closed provenance, partition, checkpoint or training validation error."""


class TrainingSpec(FrozenModel):
    run_id: UUID
    student_id: UUID
    plan_version: int = Field(ge=1)
    as_of: datetime
    market: Literal['XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'BTCUSD']
    tactic: Literal['trend', 'breakout', 'range', 'scalping', 'swing']
    epochs: int = Field(ge=1, le=80)
    learning_rate: float = Field(gt=0, le=0.1)
    seed: int = Field(ge=0, le=2**31 - 1)
    embargo_minutes: int = Field(default=240, ge=1, le=10080)
    min_train: int = Field(default=8, ge=8)
    min_validation: int = Field(default=4, ge=4)
    max_episodes: int = Field(default=2000, ge=12, le=50000)
    allow_synthetic_research: bool = True

    @field_validator('as_of')
    @classmethod
    def require_asof_utc(cls, value):
        return require_utc(value)

    @model_validator(mode='after')
    def check_minimums(self):
        if self.max_episodes < self.min_train + self.min_validation:
            raise ValueError('max_episodes below minimum split requirement')
        return self


def _jsonhash(obj) -> str:
    return sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def _vec(e) -> list[float]:
    """Signal-time *only* features; never MFE/MAE, realised P&L or close reasons."""
    tactic_ids = {s.removeprefix('tactic:') for s in e.skill_ids if s.startswith('tactic:')}
    return [float(e.market_regime == x) for x in REGIMES] + [float(e.instrument == x) for x in MARKETS] + [float(x in tactic_ids) for x in TACTICS]


def freeze_training_data(session: Session, spec: TrainingSpec) -> dict:
    """Freeze chronological TRAIN-only examples, with forward embargo between splits.

    All selected rows must pass archive hash checks. No retrieval of sealed partitions.
    S6 permits research on fixtures/quarantined historical data only, never promotion.
    """
    student = session.get(Student, str(spec.student_id))
    if student is None:
        raise TrainingError('student not found')
    plan = session.scalar(select(LearningPlan).where(LearningPlan.student_id == student.id,
                                                     LearningPlan.version == spec.plan_version))
    if plan is None:
        raise TrainingError('training plan version not found')
    if plan.mode == 'directed' and (spec.market not in plan.markets or spec.tactic not in plan.skills):
        raise TrainingError('directed student training outside CEO learning scope')
    query = (select(TradeExperience)
             .where(TradeExperience.student_id == str(spec.student_id),
                    TradeExperience.partition == ExamPartition.TRAIN.value,
                    TradeExperience.instrument == spec.market,
                    TradeExperience.available_at <= spec.as_of)
             .order_by(TradeExperience.available_at.asc(), TradeExperience.id.asc()))
    records = []
    for row in session.scalars(query):
        try:
            e = _safe_episode(row)
        except MemoryError as exc:
            raise TrainingError(f"archived episode integrity mismatch: {exc}") from exc
        if 'tactic:' + spec.tactic not in e.skill_ids:
            continue
        if e.origin not in (Origin.SYNTHETIC_FIXTURE, Origin.HISTORICAL_QUARANTINED):
            raise TrainingError('unknown or untrusted training source')
        if e.origin == Origin.SYNTHETIC_FIXTURE and not spec.allow_synthetic_research:
            raise TrainingError('synthetic research disallowed by this training job')
        if e.available_at > spec.as_of or e.closed_at > spec.as_of:
            raise TrainingError('future episode entered training dataset')
        # Explicitly distrust large or pathological labels instead of letting them dominate.
        net_r = float(e.net_r)
        if not np.isfinite(net_r):
            raise TrainingError('non-finite training label')
        records.append({'event_id': str(e.event_id), 'content_sha256': e.content_sha256,
                        'source_sha256': e.source_sha256, 'origin': e.origin.value,
                        'signal_at': e.signal_at, 'closed_at': e.closed_at,
                        'available_at': e.available_at, 'features': _vec(e),
                        'net_r': net_r, 'profitable': float(e.net_r > 0)})
    if len(records) > spec.max_episodes:
        raise TrainingError('too many episodes; specify an explicit bounded training snapshot')
    records.sort(key=lambda x: (x['signal_at'], x['event_id']))
    if len(records) < spec.min_train + spec.min_validation:
        raise TrainingError('insufficient eligible closed training examples')
    # The last 20% of TRAIN episodes is a *development* validation slice, not an
    # independent Examiner's validation/holdout set (those are never accessed).
    n_valid = max(spec.min_validation, (len(records) + 4)//5)
    valid = records[-n_valid:]
    cut = valid[0]['signal_at'] - timedelta(minutes=spec.embargo_minutes)
    train = [r for r in records[:-n_valid] if r['closed_at'] <= cut and r['available_at'] <= cut]
    if len(train) < spec.min_train:
        raise TrainingError('insufficient chronological train episodes after embargo')
    if {r['event_id'] for r in train} & {r['event_id'] for r in valid}:
        raise TrainingError('train/validation example collision')
    signature = [{'id': r['event_id'], 'hash': r['content_sha256'], 'origin': r['origin'],
                  'signal_at': r['signal_at'].isoformat(), 'available_at': r['available_at'].isoformat(),
                  'features': r['features'], 'label': r['net_r']} for r in train+valid]
    split_manifest = {'schema': 'training_split.v1', 'student_id': str(spec.student_id),
                      'as_of': spec.as_of.isoformat(), 'catalog_sha256': catalog_manifest()['catalog_sha256'],
                      'feature_schema': FEATURE_SCHEMA, 'architecture': ARCHITECTURE,
                      'train_event_ids': [r['event_id'] for r in train],
                      'development_validation_event_ids': [r['event_id'] for r in valid],
                      'embargo_minutes': spec.embargo_minutes, 'examples': signature}
    return {'train': train, 'validation': valid, 'manifest': split_manifest, 'sha256': _jsonhash(split_manifest),
            'provenance': sorted({r['origin'] for r in train+valid})}


def _model(torch):
    return torch.nn.Sequential(torch.nn.Linear(len(FEATURE_NAMES), 16), torch.nn.ReLU(), torch.nn.Linear(16, 2))


def _tensors(torch, rows):
    x = torch.tensor([r['features'] for r in rows], dtype=torch.float32)
    profit = torch.tensor([r['profitable'] for r in rows], dtype=torch.float32)
    net_r = torch.tensor([max(-5., min(5., r['net_r'])) for r in rows], dtype=torch.float32)
    return x, profit, net_r


def _loss(torch, model, tensors):
    x, profit, net_r = tensors
    output = model(x)
    return torch.nn.functional.binary_cross_entropy_with_logits(output[:, 0], profit) + 0.2 * torch.nn.functional.smooth_l1_loss(output[:, 1], net_r)


def _weights_blob(model) -> bytes:
    """Non-executable, pickle-free checkpoint serialization."""
    output = io.BytesIO()
    np.savez_compressed(output, **{k: v.detach().cpu().numpy() for k, v in model.state_dict().items()})
    data = output.getvalue()
    if len(data) > MAX_CHECKPOINT_BYTES:
        raise TrainingError('checkpoint exceeded size limit')
    return data


def _checkpoint_weights(torch, blob: bytes, model) -> None:
    if len(blob) > MAX_CHECKPOINT_BYTES:
        raise TrainingError('checkpoint exceeded size limit')
    with np.load(io.BytesIO(blob), allow_pickle=False) as archive:
        expected = model.state_dict()
        if set(archive.files) != set(expected):
            raise TrainingError('checkpoint parameter keys mismatch')
        restored = {}
        for key, current in expected.items():
            value = archive[key]
            if tuple(value.shape) != tuple(current.shape) or value.dtype != np.float32 or not np.isfinite(value).all():
                raise TrainingError('checkpoint parameter shape/type/value mismatch')
            restored[key] = torch.from_numpy(value.copy())
    model.load_state_dict(restored, strict=True)


def _safe_path(root: Path, path: str) -> Path:
    base = root.resolve()
    resolved = (base / path).resolve()
    if not resolved.is_relative_to(base):
        raise TrainingError('checkpoint path outside configured storage root')
    return resolved


def load_checkpoint(torch, root: Path, checkpoint: TrainingCheckpoint, model) -> None:
    path = _safe_path(root, checkpoint.relative_path)
    try:
        contents = path.read_bytes()
    except OSError as exc:
        raise TrainingError('checkpoint artifact unavailable') from exc
    if sha256(contents).hexdigest() != checkpoint.artifact_sha256:
        raise TrainingError('checkpoint checksum mismatch')
    try:
        _checkpoint_weights(torch, contents, model)
    except (ValueError, KeyError, OSError, TypeError, EOFError) as exc:
        raise TrainingError('checkpoint contents invalid') from exc


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tempname = tempfile.mkstemp(prefix='.staged-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Never overwrite an existing epoch; recoverability requires immutable artifacts.
        if path.exists():
            if path.read_bytes() != data:
                raise TrainingError('existing immutable checkpoint differs')
        else:
            os.replace(tempname, path)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)


def train_student(session: Session, spec: TrainingSpec, *, checkpoint_root: Path,
                  stop_after_epoch: int | None = None) -> dict:
    """Trusted offline CPU research worker. Repeated run IDs must match frozen inputs.

    Training works on the same frozen, chronological, S5 TRAIN-only snapshot. At each
    epoch checkpoint weights are persisted first, then DB metadata. Safe to retry
    after interruption at epoch boundaries; no broker/qualification writes exist.
    """
    try:
        import torch
    except ImportError as exc:
        raise TrainingError('install optional agentic-trading[training] dependency') from exc
    torch.set_num_threads(1)
    frozen = freeze_training_data(session, spec)
    cfg_hash = _jsonhash(spec.model_dump(mode='json'))
    run = session.get(TrainingRun, str(spec.run_id))
    if run is not None:
        if (run.student_id != str(spec.student_id) or run.config_sha256 != cfg_hash
            or run.snapshot_sha256 != frozen['sha256']):
            raise TrainingError('training run ID collision or changed snapshot/plan')
    else:
        run = TrainingRun(id=str(spec.run_id), student_id=str(spec.student_id),
                          config_sha256=cfg_hash, snapshot_sha256=frozen['sha256'],
                          config=spec.model_dump(mode='json'), snapshot_manifest=frozen['manifest'],
                          state='research_only', qualification='unqualified')
        session.add(run)
        session.flush()
        session.commit()
    seed = int(spec.seed)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = _model(torch)
    last = session.scalar(select(TrainingCheckpoint).where(TrainingCheckpoint.run_id == run.id)
                          .order_by(TrainingCheckpoint.epoch.desc()).limit(1))
    start = 1
    if last is not None:
        load_checkpoint(torch, checkpoint_root, last, model)
        start = last.epoch + 1
    training = _tensors(torch, frozen['train'])
    validation = _tensors(torch, frozen['validation'])
    target_epoch = min(spec.epochs, stop_after_epoch) if stop_after_epoch is not None else spec.epochs
    if target_epoch < 1 or target_epoch > spec.epochs:
        raise TrainingError('invalid stop_after_epoch')
    for epoch in range(start, target_epoch + 1):
        model.train()
        model.zero_grad(set_to_none=True)
        objective = _loss(torch, model, training)
        objective.backward()
        with torch.no_grad():
            for p in model.parameters():
                if p.grad is None or not torch.isfinite(p.grad).all():
                    raise TrainingError('non-finite gradient')
                p.add_(p.grad, alpha=-float(spec.learning_rate))
        model.eval()
        with torch.no_grad():
            train_loss = float(_loss(torch, model, training).item())
            dev_loss = float(_loss(torch, model, validation).item())
        if not np.isfinite(train_loss) or not np.isfinite(dev_loss):
            raise TrainingError('non-finite training metric')
        blob = _weights_blob(model)
        path_relative = f'{spec.student_id}/{spec.run_id}/epoch-{epoch:04d}.npz'
        path = _safe_path(checkpoint_root, path_relative)
        _atomic_write(path, blob)
        session.add(TrainingCheckpoint(run_id=run.id, epoch=epoch,
                                       relative_path=path_relative, artifact_sha256=sha256(blob).hexdigest(),
                                       snapshot_sha256=frozen['sha256'],
                                       train_loss=train_loss, development_loss=dev_loss))
        session.commit()
    checkpoints = session.scalars(select(TrainingCheckpoint).where(TrainingCheckpoint.run_id == run.id)
                                   .order_by(TrainingCheckpoint.epoch.asc())).all()
    # Verify entire chain of checkpoint artifacts, not just latest; fail closed on tampering.
    for cp in checkpoints:
        if cp.snapshot_sha256 != frozen['sha256'] or cp.epoch < 1 or cp.epoch > spec.epochs:
            raise TrainingError('checkpoint metadata inconsistent with frozen research run')
        contents = _safe_path(checkpoint_root, cp.relative_path).read_bytes()
        if sha256(contents).hexdigest() != cp.artifact_sha256:
            raise TrainingError('checkpoint artifact modified or missing')
    return {'run_id': run.id, 'student_id': run.student_id, 'state': 'research_only',
            'qualification': 'unqualified', 'research_eligible': False,
            'snapshot_sha256': run.snapshot_sha256, 'config_sha256': run.config_sha256,
            'train_examples': len(frozen['train']), 'development_validation_examples': len(frozen['validation']),
            'provenance': frozen['provenance'], 'epoch': checkpoints[-1].epoch if checkpoints else 0,
            'epochs_planned': spec.epochs, 'metrics': [dict(epoch=c.epoch, train_loss=c.train_loss,
              development_loss=c.development_loss, checkpoint_sha256=c.artifact_sha256) for c in checkpoints],
            'note': 'Synthetic/quarantined research only; development validation is not an independent exam.'}


def student_training_runs(session: Session, student_id: str, limit: int = 20) -> list[dict]:
    if not 1 <= limit <= 100:
        raise TrainingError('limit must be 1..100')
    runs = session.scalars(select(TrainingRun).where(TrainingRun.student_id == student_id)
                           .order_by(TrainingRun.created_at.desc(), TrainingRun.id.desc()).limit(limit)).all()
    outputs = []
    for run in runs:
        checkpoints = session.scalars(select(TrainingCheckpoint).where(TrainingCheckpoint.run_id == run.id)
                                       .order_by(TrainingCheckpoint.epoch.asc())).all()
        if (run.config_sha256 != _jsonhash(run.config) or run.snapshot_sha256 != _jsonhash(run.snapshot_manifest)
            or run.state != 'research_only' or run.qualification != 'unqualified'):
            raise TrainingError('training metadata integrity failure')
        outputs.append({'run_id': run.id, 'student_id': run.student_id, 'state': run.state,
                        'qualification': run.qualification, 'config': run.config,
                        'snapshot_sha256': run.snapshot_sha256, 'epoch': checkpoints[-1].epoch if checkpoints else 0,
                        'metrics': [{'epoch': c.epoch, 'train_loss': c.train_loss,
                                     'development_loss': c.development_loss} for c in checkpoints],
                        'research_eligible': False})
    return outputs
