# Sprint 7 — PDCA / Checker acceptance

**Plan.** Independent, source- and model-scoped exam with common execution conditions, after-cost net financial metrics, chronological embargo, immutable report retention, and CEO read-only display. Research-only by construction.

**Do.** `examiner.py`, SQLAlchemy `ExamRun`, Alembic `0005_s7`, `/v1/students/{student_id}/exams`, `Students → Exams` interface, tests and docs.

**Check.** Full backend tests, fresh Alembic upgrade and repeat-safe schema, CI frontend TypeScript/mobile checks. Verify 100+ deliberately profitable synthetic trades **remain unqualified**; source spoof, wrong student, altered model/order snapshots, window leakage, incomplete checkpoint, mismatched costs, tampered DB report and re-used exam ID fail closed.

**Act / blocked.** Dataset licensing/independent verification, genuinely sealed holdout, multiple-trial selection mitigation, independently reproduced financial results and Registrar promotion are **not implemented**; no publication of profitability claims, qualified research, paper or live trading.

**Status.** Offline numeric examination prototype available; until verified data gate opens, qualification is deliberately impossible. PR remains draft pending CEO review.
