# Sprint 6 — PDCA / Checker acceptance

**Plan:** Independent per-student CPU PyTorch baseline; bounded training-only as-of snapshots; chronological development split; validated weight checkpoint recovery; CEO-readable chart; no trading or automatic promotion.

**Do:** `neural_training.py`, SQLAlchemy `TrainingRun/TrainingCheckpoint`, Alembic `0004_s6`, offline CLI, authenticated research-history API and Student Training panel.

**Check:** Run all backend regressions, clean Alembic migration, test checkpoint determinism and interruption recovery, no future/holdout access, tamper fail-closed, directed plan scope and no research promotion. Run CI backend/frontend/mobile.

**Act / outstanding:** 12-month licensed historical data remains unverified; M1 bid/ask data and execution assumptions not independently audited. `S7 Examiner` needed for qualification. Orchestrator scheduling only in S8. No training against real independently verified data, no live or paper permissions.

**Status:** Local implementation awaiting remote CI checks and Checker approval. Do not merge before review.
