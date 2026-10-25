# Changelog

## 0.0.1 — 2026-10-25 — Sprint 0 foundation

- Initial independent Agentic Trading local development scaffold.
- Added FastAPI health/capabilities endpoints (all trading disabled).
- Defined core versioned contracts for events, trade proposals, CEO approvals and research exam evidence.
- Added fail-closed research gate checks and snapshot schemas.
- Added pytest tests, CI workflow definition, architecture/security/data-provider/UX documentation.

**Release scope:** Local source scaffold only. No GitHub remote publication, hosted deployment, licensed market data, strategy training or broker connectivity. All future schema/permission changes require regression tests and approved release review.

**Rollback:** Restore the initial local Git commit or unpack the Sprint 0 archive. No production state or database migration is involved.


## 0.1.0 — 2026-10-25 — Sprint 1 development candidate

- CEO-only Argon2 login with signed HttpOnly sessions, CSRF/origin protections and bootstrap procedure.
- Persistent student UUIDs, unique names, autonomous/directed plan versions, rename and audit events.
- SQLite dev and PostgreSQL-compatible Alembic schema migration.
- Responsive Home / Students / Trading React/TypeScript app with no fabricated results or trading controls.
- 23 local/backend CI checks, frontend production build and mobile Chromium Playwright full-flow test passed.

**Release scope:** Source code on Sprint 1 draft PR; owner review and merge required. Not deployed. All trading execution disabled. Production infrastructure/security and Postgres integration are separate gates.

## 2026-10-25 — Sprint 2 implementation
- XAUUSD M15 strict CSV import; SHA-256 raw/canonical frozen storage, provenance/quality reports, completed H1/H4 context.
- Home Data Engine upload panel and quarantined-source status.
- Preserve research/trading disablement. External licensed provider verification remains pending.

## Sprint 5 — Skill Library and episodic memory (proposed)
- Versioned market, tactic and risk skills with prerequisite graph and content digest.
- Immutable research closed-trade episodes, costs-derived Good / Bad / Flat, student-isolated time-safe recall excluding validation/holdout.
- SQL append-only-by-service archive, tamper checks, idempotent internal writes and Alembic migration.
- Read-only CEO skill/memory API and responsive student profile panels. Training and qualification remain disabled.
