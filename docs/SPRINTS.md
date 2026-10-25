# Sprint Tracker (PDCA)

Source of truth: `docs/PRODUCT_SPEC_v1.0.md` Sprint Backlog. No sprint complete until independently checked and demonstrated.

| Sprint | Deliverable | Status |
|---|---|---|
| S0 | Repo skeleton, contracts, policy tests, docs, provider shortlist, UX wireframes | **Completed — published, verified in GitHub** |
| S1 | Login, CEO role, student creation, persistent plans, main shell | **Verified development foundation — PR review pending, not deployed** |
| S2 | Verified XAUUSD Data Engine | Not started |
| S3 | Historical execution simulator | Not started |
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
