"""Sprint 6: experimental per-student neural challenger training and recoverable checkpoints.

No HTTP training route. Never qualifies a model, changes Guardian or executes trades.
The ONLY eligible training origin in S6 is a synthetic development fixture, under
an explicit environment guard. Independent validation is reserved for Sprint 7.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from agentic_trading.contracts.common import require_utc
from agentic_trading.skills_memory import (
    CATALOG, ClosedTradeEpisode, ExamPartition, Origin, _safe_episode,
)
from agentic_trading.storage import Student, TradeExperience, TrainingRun


SCHEMA = 'experimental_mlp_checkpoint.v1'
REGIMES = ('TREND_UP', 'TREND_DOWN', 'RANGE', 'CHOP', 'UNCERTAIN')
MARKETS = ('XAUUSD', 'EURUSD', 'GBPUSD', 'US500', 'NAS100', 'BTCUSD')
TACTICS = ('trend', 'breakout', 'range', 'scalping', 'swing')
FEATURES = tuple('regime:' + x for x in REGIMES) + tuple('market:' + x for x in MARKETS) + tuple('tactic:' + x for x in TACTICS)
MODEL_VERSION = 'signal_context_mlp.v1'


class NeuralTrainingError(ValueError):
    """Fail-closed training input, checkpoint, eligibility or consistency failure."""


class TrainingPaused(RuntimeError):
    """Testing/internal interruption *after* a recoverable epoch snapshot is written."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                             allow_nan=False).encode('utf-8')).hexdigest()


def _safe_json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 1_500_000:
        raise NeuralTrainingError('checkpoint missing or exceeds size limit')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or set(value) != {'payload', 'sha256'} or not isinstance(value['payload'], dict) or value['sha256'] != _digest(value['payload']):
            raise NeuralTrainingError('checkpoint hash or envelope mismatch')
        return value['payload']
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, OverflowError) as exc:
        raise NeuralTrainingError('checkpoint is invalid or tampered') from exc


def _atomic_json(path: Path, payload: dict) -> str:
    """0600, flush+fsync, atomic replace: a process interruption cannot expose partial JSON."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    envelope = {'payload': payload, 'sha256': _digest(payload)}
    data = (json.dumps(envelope, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    name = None
    try:
        fd, name = tempfile.mkstemp(prefix='.checkpoint-', dir=path.parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        name = None
        if hasattr(os, 'O_DIRECTORY'):
            dirfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)
    return envelope['sha256']


@dataclass(frozen=True)
class TrainingSettings:
    student_id: str
    market: str
    tactic: str
    as_of: datetime
    seed: int = 42
    epochs: int = 20
    learning_rate: float = 0.04

    def __post_init__(self):
        try:
            UUID(self.student_id)
            require_utc(self.as_of)
        except (ValueError, TypeError) as exc:
            raise NeuralTrainingError('student and as_of must have valid identifiers/UTC time') from exc
        if self.market not in MARKETS or self.tactic not in TACTICS:
            raise NeuralTrainingError('unknown market or tactic')
        if not (0 <= self.seed < 2**31 and isinstance(self.seed, int)):
            raise NeuralTrainingError('invalid random seed')
        if not (2 <= self.epochs <= 50 and isinstance(self.epochs, int)):
            raise NeuralTrainingError('epochs must be between 2 and 50')
        if not (math.isfinite(self.learning_rate) and 0 < self.learning_rate <= 0.1):
            raise NeuralTrainingError('learning rate out of bounds')

    def descriptor(self) -> dict:
        return {
            'market': self.market, 'tactic': self.tactic, 'as_of': self.as_of.isoformat(),
            'seed': self.seed, 'epochs': self.epochs, 'learning_rate': self.learning_rate,
            'model_version': MODEL_VERSION, 'feature_schema': list(FEATURES),
        }


def _vector(episode: ClosedTradeEpisode) -> list[float]:
    """Only information known at signal time is allowed as a model input."""
    return ([float(episode.market_regime == x) for x in REGIMES]
            + [float(episode.instrument == x) for x in MARKETS]
            + [float('tactic:' + x in episode.skill_ids) for x in TACTICS])


def _label(episode: ClosedTradeEpisode) -> tuple[float, float]:
    # Preserve the sign and all magnitudes but limit extreme numeric influence via sign-log.
    outcome_r = float(episode.net_r)
    if not math.isfinite(outcome_r):
        raise NeuralTrainingError('nonfinite training label')
    return math.copysign(math.log1p(abs(outcome_r)), outcome_r), float(episode.net_pnl_usd > 0)


def _eligible(session: Session, cfg: TrainingSettings):
    student = session.scalar(select(Student).options(selectinload(Student.plans)).where(Student.id == cfg.student_id))
    if student is None or not student.plans:
        raise NeuralTrainingError('student or plan not found')
    current_plan = max(student.plans, key=lambda p: p.version)
    if current_plan.mode == 'directed' and (cfg.market not in current_plan.markets or cfg.tactic not in current_plan.skills):
        raise NeuralTrainingError('requested experiment is outside CEO-directed scope')
    rows = session.scalars(select(TradeExperience).where(
        TradeExperience.student_id == cfg.student_id,
        TradeExperience.partition == ExamPartition.TRAIN.value,
        TradeExperience.available_at <= cfg.as_of,
    ).order_by(TradeExperience.available_at.asc(), TradeExperience.id.asc())).all()
    episodes: list[ClosedTradeEpisode] = []
    for row in rows:
        episode = _safe_episode(row)  # Full provenance and stored payload tamper verification.
        if episode.instrument != cfg.market or 'tactic:' + cfg.tactic not in episode.skill_ids:
            continue
        if episode.origin != Origin.SYNTHETIC_FIXTURE or not episode.source_id.startswith('fixture:'):
            raise NeuralTrainingError('S6 does not train on quarantined or unverified market data')
        episodes.append(episode)
    episodes.sort(key=lambda e: (e.signal_at, e.available_at, str(e.event_id)))
    if len(episodes) < 16:
        raise NeuralTrainingError('at least 16 closed independent research episodes are required')
    # Validation is a development diagnostic only. It is NOT Examiner holdout evidence.
    split = int(len(episodes) * .75)
    while split < len(episodes) and episodes[split - 1].signal_at == episodes[split].signal_at:
        split += 1  # Keep the same timestamp out of both sets.
    if split >= len(episodes):
        raise NeuralTrainingError('insufficient distinct chronological validation signals')
    first_validation_at = episodes[split].signal_at
    train = [e for e in episodes[:split] if e.available_at < first_validation_at]
    validation = episodes[split:]
    # Overlapping trade outcomes or post-cutoff labels must never influence train weights.
    if len(train) < 8 or len(validation) < 4:
        raise NeuralTrainingError('insufficient purged chronological train/validation examples')
    if any(e.available_at >= first_validation_at for e in train) or any(e.signal_at < first_validation_at for e in validation):
        raise NeuralTrainingError('chronological split invariant failed')
    return current_plan.version, train, validation, len(episodes) - len(train) - len(validation)


def _network(torch):
    return torch.nn.Sequential(torch.nn.Linear(len(FEATURES), 16), torch.nn.Tanh(),
                               torch.nn.Linear(16, 2))


def _weights(model) -> dict:
    return {k: v.detach().cpu().tolist() for k, v in model.state_dict().items()}


def _load_weights(torch, model, mapping):
    if not isinstance(mapping, dict) or set(mapping) != set(model.state_dict()):
        raise NeuralTrainingError('checkpoint model parameters are inconsistent')
    state = {}
    for key, old in model.state_dict().items():
        try:
            new = torch.as_tensor(mapping[key], dtype=torch.float32)
        except (TypeError, ValueError) as exc:
            raise NeuralTrainingError('checkpoint weights invalid') from exc
        if new.shape != old.shape or not bool(torch.isfinite(new).all()):
            raise NeuralTrainingError('checkpoint weights changed shape or are nonfinite')
        state[key] = new
    model.load_state_dict(state, strict=True)


def _verify_snapshot(snapshot: dict, key: str, provenance: str, epoch_max: int, model, torch):
    if (snapshot.get('schema_version') != SCHEMA or snapshot.get('experiment_key') != key
        or snapshot.get('provenance_hash') != provenance or snapshot.get('feature_schema') != list(FEATURES)
        or type(snapshot.get('epoch')) is not int or not (1 <= snapshot['epoch'] <= epoch_max)
        or not isinstance(snapshot.get('curve'), list) or len(snapshot['curve']) != snapshot['epoch']):
        raise NeuralTrainingError('checkpoint metadata failed validation')
    for i, item in enumerate(snapshot['curve'], start=1):
        if (not isinstance(item, dict) or item.get('epoch') != i or
            not all(isinstance(item.get(k), (int, float)) and math.isfinite(item[k]) and item[k] >= 0
                    for k in ('train_loss', 'validation_loss'))):
            raise NeuralTrainingError('checkpoint learning curve is invalid')
    _load_weights(torch, model, snapshot.get('weights'))


def _summarise(row: TrainingRun) -> dict:
    summary = row.training_summary
    if (row.state != 'experimental_only' or row.checkpoint_hash != summary.get('checkpoint_sha256')
        or row.experiment_key != summary.get('experiment_key')
        or row.provenance_hash != summary.get('provenance_hash')
        or row.plan_version != summary.get('plan_version')
        or row.student_id != summary.get('student_id')):
        raise NeuralTrainingError('training registry metadata integrity mismatch')
    return {**summary, 'training_run_id': row.id, 'created_at': row.created_at.isoformat(),
            'qualification': 'unqualified', 'research_eligible': False,
            'exam_eligible': False, 'deployment_eligible': False}


def student_training_history(session: Session, student_id: str, storage_root: Path, limit: int = 20) -> dict:
    if not 1 <= limit <= 100:
        raise NeuralTrainingError('training history limit must be 1..100')
    rows = session.scalars(select(TrainingRun).where(TrainingRun.student_id == student_id)
                           .order_by(TrainingRun.created_at.desc(), TrainingRun.id.desc()).limit(limit)).all()
    output = []
    for row in rows:
        expected_path = _checkpoint_path(storage_root, row.student_id, row.experiment_key)
        if row.checkpoint_path != str(expected_path.relative_to(storage_root)):
            raise NeuralTrainingError('training registry checkpoint path mismatch')
        payload = _safe_json(expected_path)
        if (row.checkpoint_hash != _digest(payload) or payload.get('experiment_key') != row.experiment_key
            or payload.get('provenance_hash') != row.provenance_hash
            or payload.get('schema_version') != SCHEMA
            or payload.get('feature_schema') != list(FEATURES)
            or payload.get('curve') != row.training_summary.get('curve')
            or payload.get('epoch') != row.training_summary.get('epochs_completed')):
            raise NeuralTrainingError('training registry checkpoint checksum/curve mismatch')
        output.append(_summarise(row))
    return {'student_id': student_id, 'runs': output, 'qualification': 'unqualified',
            'note': 'Experimental training only. Curves are NOT independent profitability or mastery evidence.'}


def _checkpoint_path(root: Path, student_id: str, experiment_key: str) -> Path:
    # The only dynamic path components are validated stable UUID and a SHA-256.
    UUID(student_id)
    if len(experiment_key) != 64 or any(c not in '0123456789abcdef' for c in experiment_key):
        raise NeuralTrainingError('invalid experiment identifier')
    return root / 'research_training' / student_id / experiment_key / 'completed.json'


def run_fixture_training(session: Session, storage_root: Path, cfg: TrainingSettings,
                         *, environment: str, explicit_fixture_authorisation: bool = False,
                         interrupt_after_epoch: int | None = None) -> dict:
    """Trusted offline worker entrypoint. HTTP callers never invoke this function.

    `interrupt_after_epoch` is for tests of crash/resume, not a scheduling API.
    """
    if environment != 'development' or not explicit_fixture_authorisation:
        raise NeuralTrainingError('synthetic training requires explicit local development authorisation')
    if interrupt_after_epoch is not None and not (1 <= interrupt_after_epoch < cfg.epochs):
        raise NeuralTrainingError('invalid simulated interruption epoch')
    try:
        import torch
        import torch.nn.functional as F
    except ImportError as exc:
        raise NeuralTrainingError('optional torch dependency missing: install backend[ml]') from exc
    plan_version, train, validation, purged = _eligible(session, cfg)
    provenance = _digest({'train': [(str(e.event_id), e.content_sha256) for e in train],
                          'validation': [(str(e.event_id), e.content_sha256) for e in validation]})
    key = _digest({'student_id': cfg.student_id, 'plan_version': plan_version,
                   'settings': cfg.descriptor(), 'provenance': provenance})
    target = _checkpoint_path(storage_root, cfg.student_id, key)
    existing = session.scalar(select(TrainingRun).where(TrainingRun.experiment_key == key))
    if existing is not None:
        if existing.student_id != cfg.student_id or existing.checkpoint_path != str(target.relative_to(storage_root)):
            raise NeuralTrainingError('completed training record has mismatched student or storage path')
        saved = _safe_json(target)
        if (existing.checkpoint_hash != _digest(saved) or saved.get('experiment_key') != key
            or saved.get('provenance_hash') != provenance
            or saved.get('curve') != existing.training_summary.get('curve')
            or saved.get('epoch') != cfg.epochs):
            raise NeuralTrainingError('completed checkpoint/registry integrity mismatch')
        return _summarise(existing)

    x_train = torch.tensor([_vector(e) for e in train], dtype=torch.float32)
    y_train = torch.tensor([_label(e) for e in train], dtype=torch.float32)
    x_val = torch.tensor([_vector(e) for e in validation], dtype=torch.float32)
    y_val = torch.tensor([_label(e) for e in validation], dtype=torch.float32)

    def objective(pred, label):
        return F.smooth_l1_loss(pred[:, 0], label[:, 0]) + .2 * F.binary_cross_entropy_with_logits(pred[:, 1], label[:, 1])

    # Stable seed / fixed full batch / no momentum or dropout: the next epoch is
    # reproducible from its saved weights without unsafe pickled optimizer state.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(cfg.seed)
        model = _network(torch)
        optimizer = torch.optim.SGD(model.parameters(), lr=cfg.learning_rate)
        progress = target.with_name('progress.json')
        epoch_start = 0
        curve = []
        if progress.exists():
            prior = _safe_json(progress)
            _verify_snapshot(prior, key, provenance, cfg.epochs, model, torch)
            epoch_start = prior['epoch']
            curve = prior['curve']
        for epoch in range(epoch_start + 1, cfg.epochs + 1):
            model.train()
            optimizer.zero_grad(set_to_none=True)
            loss = objective(model(x_train), y_train)
            if not bool(torch.isfinite(loss)):
                raise NeuralTrainingError('training loss is nonfinite')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            model.eval()
            with torch.no_grad():
                train_loss = float(objective(model(x_train), y_train).item())
                val_loss = float(objective(model(x_val), y_val).item())
            if not (math.isfinite(train_loss) and math.isfinite(val_loss)):
                raise NeuralTrainingError('nonfinite learning diagnostics')
            curve.append({'epoch': epoch, 'train_loss': train_loss, 'validation_loss': val_loss})
            snapshot = {'schema_version': SCHEMA, 'experiment_key': key,
                        'provenance_hash': provenance, 'feature_schema': list(FEATURES),
                        'epoch': epoch, 'curve': curve, 'weights': _weights(model)}
            _atomic_json(progress, snapshot)
            if interrupt_after_epoch == epoch:
                raise TrainingPaused(f'recoverable snapshot saved after epoch {epoch}')
        final_snapshot = _safe_json(progress)
        _verify_snapshot(final_snapshot, key, provenance, cfg.epochs, model, torch)
        if final_snapshot['epoch'] != cfg.epochs:
            raise NeuralTrainingError('training stopped before requested epochs')
        digest = _atomic_json(target, final_snapshot)

    # Persist a complete immutable provenance & learning curve record, never scores
    # that could be mistaken for an independent test or approved strategy.
    summary = {
        'schema_version': 'training_summary.v1', 'student_id': cfg.student_id,
        'experiment_key': key, 'provenance_hash': provenance, 'plan_version': plan_version,
        'checkpoint_sha256': digest, 'model_version': MODEL_VERSION,
        'market': cfg.market, 'tactic': cfg.tactic, 'origin': 'synthetic_fixture',
        'partition': 'internal_chronological_diagnostic', 'epochs_completed': cfg.epochs,
        'train_examples': len(train), 'validation_examples': len(validation),
        'purged_count': purged,
        'curve': curve, 'seed': cfg.seed, 'as_of': cfg.as_of.isoformat(),
    }
    row = TrainingRun(id=str(UUID(bytes=bytes.fromhex(key[:32]))), student_id=cfg.student_id,
                      plan_version=plan_version, skill_id='tactic:' + cfg.tactic,
                      instrument=cfg.market, experiment_key=key, provenance_hash=provenance,
                      checkpoint_hash=digest, checkpoint_path=str(target.relative_to(storage_root)),
                      training_summary=summary, state='experimental_only')
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise NeuralTrainingError('concurrent training run collision') from exc
    return _summarise(row)
