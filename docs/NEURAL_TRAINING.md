# Sprint 6 — Neural research training and recoverable checkpoints

## Scope / safety status

**Built:** Offline CPU-only PyTorch MLP baseline (16 signal-time features, 16 hidden units, 2 heads for Good-vs-non-Good and clipped net R); closed-memory feature extractor; bounded chronological training/development split with 240-minute default embargo; strict TRAIN-partition access; training snapshot and configuration SHA-256; per-epoch immutable NumPy `.npz` weight checkpoints; deterministic SGD; recovery from last saved epoch; SQL/Alembic run/epoch metrics; CEO-authenticated read-only training history with learning-loss chart.

**Not built:** Academy orchestration, automatic long-running workers, neural trading inference in live execution, independent Examiner, research champion promotion, validated historical source, paper trading or live trading. S6 does **not** automatically train when a student is created. Creating a plan or obtaining a low development loss is **never** graduation evidence.

## Data and anti-leakage rules

- Only S5 `trade_experiences` records from `partition=train` with `closed_at` and `available_at` at or before the specified UTC `as_of` are read. Every retrieved archived event is hash-verified against its canonical typed payload.
- Only the specified student, market, tactic and existing version of their learning plan can be selected. Directed students cannot train outside CEO-assigned markets and tactics.
- Input features are restricted to recorded market regime (5 one-hot values), market (6) and tactic family (5), values intended to have been known **when the proposal was made**. No future return, MFE/MAE, close reason, after-cost P&L, fee, outcome or holding duration is included in inputs.
- Labels come from CLOSED trades only: Good/not-Good after costs, plus net realised R clipped to [-5, 5] for robustness. All calculation is purely experimental.
- Last 20% of the *TRAIN* partition is a local development-validation slice. Earlier training episodes must close and be available at least 240 minutes before that validation slice begins; otherwise they are purged. This is not the Examiner's independent validation or holdout dataset; partitions in S5 are not yet independently verified.
- Synthetic fixtures and previously quarantined historical data can only be used as **unqualified research**. Any real-data or licensing claims require separately verified provenance (S2), replay (S3), and independent examination (S7).
- An immutable manifest records exact example IDs, hashes, available timestamps, model architecture, feature schema, Skill Library hash, development partition, labels, and embargo. Changes to a run's config/snapshot invalidate resume.
- Training is deliberately full-batch CPU deterministic SGD without momentum: no opaque pickled optimizer state. Each epoch is a durable resume boundary. Same source snapshot + seed + hyperparameters yields equal model weight hashes on the same platform/runtime.

## Checkpoints and privacy

- Model weights are in `.npz` with NumPy `allow_pickle=False`, SHA-256 checksum, expected tensor names/dtypes/shapes, and finiteness checks. Never call unsafe `torch.load` on untrusted objects.
- Each epoch is written to a unique path under a user-configured private checkpoint directory, using fsync and atomic rename before metadata commit. Rerunning a job validates previous file checksums and resumes from the next epoch. Avoid concurrent writes to the same run ID until S8 leases/queues are implemented.
- Checkpoint artifacts are explicitly ignored by Git; no models, datasets, broker credentials or user data should be published to the public repository.
- The read-only API exposes epoch/train-loss/development-loss metadata only to the authenticated CEO: `GET /v1/students/{id}/training`.
- `research_training_enabled` / `automatic_training_enabled` remain `false` in API capabilities. An **offline research trainer** is available explicitly.

## Local usage (with existing research memories)

```bash
pip install -e './backend[dev,training]'
cd backend && alembic upgrade head && cd ..
python scripts/train_student_offline.py \
  --student-id <existing-student-uuid> \
  --run-id <new-job-uuid> \
  --as-of 2026-10-01T00:00:00+00:00 \
  --plan-version 1 --market XAUUSD --tactic trend \
  --epochs 12 --checkpoint-root ./model_store
```

Use the **same** run ID and exact arguments to resume, never new arguments under an existing ID. There must be at least eight train and four development examples surviving the cutoff/embargo. The command cannot trade.

## Open risks for S7/S8

- Data-use rights, verified provider lineage and independently frozen split manifests remain unclosed.
- Neural features are deliberately rudimentary, not a proven edge; use true as-of price/volume features only after a leakage-audited feature pipeline exists.
- Fixed in-process CPU training is not a distributed, recoverable job scheduler; add worker leases, heartbeats, backpressure, checkpoints across machines and load limits in S8.
- PostgreSQL production policy, object storage, audit signatures, backup/restore, and authorization remain deployment gates.
- Training curves are loss metrics, NOT after-cost realized profits, exam scores, probabilities of profitability, or market performance. No live approval follows from training.
