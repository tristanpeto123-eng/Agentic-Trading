# Sprint 6 — Experimental Neural Training

## Current scope

This stage builds a **real PyTorch model-learning and automatic checkpoint mechanism**, not an agent qualified to trade. It trains a small student-specific MLP with two supervised outputs: (a) sign-log of realized **net R after costs** and (b) whether realized net P&L was Good. The training loss combines SmoothL1 and weighted logistic BCE. These outcomes are only labels: input features deliberately include **signal-time market regime, instrument and tactic presence only**, excluding post-close gross/net P&L, MFE/MAE, exit reason and forward candles. This is a deliberately weak baseline; no claim of predictive skill is warranted.

### Strict data constraints

- **Only synthetic fixtures in explicit local development mode.** A quarantined provider import is rejected outright. No real data is independently qualified as of this sprint.
- Only the student's own `train` partition episodes with `available_at <= as_of` may be considered. Validation and independent holdout memory partitions are not included.
- Chronological internal train/validation split; overlapping or label-late earlier episodes are purged if their outcome was not available strictly before the first validation signal. The internal validation loss is **not** an independent Examiner result.
- Bound maximum epochs (50) and learning rate (0.1) and keep results unqualified. No automatic retrain, model deployment, paper/live trading, market-data qualification, or research-champion promotion.

### Checkpoints and recovery

Every epoch writes an atomic 0600 JSON file under `DATA_STORAGE_DIR/research_training/<student UUID>/<experiment SHA-256>/progress.json`; fsync precedes rename. The snapshot includes fixed feature schema, model weights, experiment key, provenance fingerprint, loss curve and epoch. Loading validates exact schema, hash and finite tensor shapes. No Python `pickle` / `torch.load` untrusted binary deserialization. Restart continues with the saved model weights and no optimizer state, because this baseline uses **fixed full-batch SGD without momentum or dropout**. A fixed seed makes a resumed run reproduce an uninterrupted run in the same environment; PyTorch/hardware changes can change floating-point results.

On successful completion, a separate `completed.json` is written and its SHA-256-payload digest and relative path are registered in `training_runs`. Repeated identical requests return the validated existing run; changes to training plan, memory evidence, as-of cutoff or parameters create a new research experiment. This is checksum-based tamper detection, **not a cryptographic signature against an attacker who controls both database and filesystem**. DB and artifact permissions remain essential.

### Safe local use

Install `pip install -e './backend[dev,ml]'`, create / migrate a local DB and seed an existing student with >=16 **closed synthetic** training episodes through trusted internal test utilities. Run:

```bash
APP_ENV=development DATABASE_URL=sqlite:////absolute/path/to/dev.sqlite3 DATA_STORAGE_DIR=/absolute/data \
 python scripts/train_fixture_student.py --student STUDENT_UUID --market XAUUSD --tactic trend \
 --as-of 2025-06-01T00:00:00Z --epochs 20 --dev-fixtures
```

The only application endpoint is **authenticated read-only** `GET /v1/students/{student_id}/training`. No API route can start neural training. Student > Training displays curve, cohort size, model version and the unqualified status.

### Limitations & open gates

1. The model uses very limited categorical features; it is not yet Scout A's multi-output regime network, nor a production-quality Scout B with rich completed price features. This must be extended and independently assessed.
2. No true 12-month licensed XAUUSD source is verified or research-eligible. No training based on real market data is enabled.
3. No distributed training lock, background job queue, early stopping, orchestrated cadence or shared model registry promotion. Those depend on later Academy infrastructure.
4. Internal diagnostic loss curves cannot establish economic profitability, statistical significance or broker execution realism. S7 Examiner requires frozen independent real-data tests and separate qualification rules.
