# Sprint Tracker (PDCA)

Source of truth: `docs/PRODUCT_SPEC_v1.0.md` Sprint Backlog. No sprint complete until independently checked and demonstrated.

| Sprint | Deliverable | Status |
|---|---|---|
| S0 | Repo skeleton, contracts, policy tests, docs, provider shortlist, UX wireframes | **Completed — published, verified in GitHub** |
| S1 | Login, CEO role, student creation, persistent plans, main shell | **Completed — CEO approved, merged into main** |
| S2 | XAUUSD historical data ingestion, quality & time-safe context | **Implementation in review; provider/rights gate pending** |
| S3 | Historical execution simulator | **Fixture engine implemented, awaiting CI & independent data/source integration** |
| S4 | Scout A/B, Strategist B, Guardian A | Not started |
| S5 | Skill/memory engine | Not started |
| S6 | Neural training and checkpoints | Not started |
| S7 | Independent Examiner | Not started |
| S8 | Autonomous Academy | Not started |
| S9 | Evolution, peer teaching, mentorship | Not started |
| S10 | CEO UX + Sentinel hardening | Not started |
| S11 | CEO-authorised paper pilot | Not started |

## Sprint 0 — PDCA

**Plan:** Independent research-only repository. Core event, proposal, decision and promotion schemas. No live execution code. Data-provider shortlist and three-tab wireframes.

**Do:** FastAPI read-only /health and /v1/capabilities; Pydantic versioned contracts; pure policy functions; pytest; GitHub Actions CI definition; engineering docs.

**Check:** Unit tests must demonstrate UTC/time visibility, revision binding, deny-veto, exact approval scope, and no synthetic promotion. API tests ensure execution endpoints absent. Verify independent codebase and no secrets/data imports. Record test evidence in `docs/SPRINT0_CHECK.md`.

**Act:** Triage Checker findings, secure repo hosting, select S1 hosting/job queue, implement authenticated persistent student creation in S1. S0 is not accepted merely because files exist.


## Sprint 1 — PDCA

**Plan:** Deliver a CEO-only, mobile-first app with persistent named students, independent identity, case-insensitive unique names, directed/autonomous versioned plans, and strict trading inactivity.

**Do:** React + TypeScript frontend with Home / Students / Trading, API authenticated CEO, Argon2 bootstrap, signed HttpOnly sessions and CSRF, SQLite local / PostgreSQL migration, audit events, CI TypeScript build.

**Check:** Verify login denial/role, CSRF, name conflicts and restarts, directed plan history, rename preserving UUID, migration idempotency, no execution endpoints, mobile layout and CI build. Evidence is in `docs/SPRINT1_CHECK.md`.

**Act:** Only after Checker acceptance, implement S2 verified market data and its provenance. Design decisions about hosted database/backups, production auth throttling and queue remain gated before public deployment.

## Sprint 2 — PDCA

**Plan:** Freeze real XAUUSD M15 CSV source content, log price basis/rights/provenance, detect malformed/gapped data, derive only completed H1/H4 and keep unverified sources quarantined.

**Do:** CEO-only import/list/context routes, SQLAlchemy/Alembic dataset metadata, SHA-256-addressed storage, quality reports and Home import UI.

**Check:** Full pytest suite, migration, checksum integrity, origin/CSRF, UTC and as-of leaks, no execution endpoints; CI frontend build and browser test. See `docs/SPRINT2_CHECK.md`.

**Act:** Get genuinely licensed real provider export and verify coverage and rights before marking provider gate complete or proceeding to production replay. Synthetic input is never accepted as qualified evidence.

## Sprint 3 — PDCA

**Plan:** Conservative M1 bid/ask historical execution with explicit costs, Guardian/Scout B binding, immutable reproducibility hashes and no future data.

**Do:** Pure `simulator.py`, synthetic-only demo, deterministic trade/ledger records and documentation.

**Check:** Unit/regression scenarios, GitHub backend/frontend/mobile CI and source-integrity gate tracked in `docs/SPRINT3_CHECK.md`.

**Act:** Connect verified S2 data and S4 decision generation only after separate safety gates. Do not equate synthetic fixture profits with investable evidence or start paper trading.
