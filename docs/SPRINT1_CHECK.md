# Sprint 1 — Checker Report (PDCA)

**Date:** 2026-10-25. **Scope:** CEO authentication, persistent student identity, learning direction, three-tab app shell. No financial capabilities, market data or training.

## Plan

S1 product-spec gate: Create and reopen student after restart, reject duplicate names, preserve plan versions and student UUID on CEO learning-direction changes; mobile Home / Students / Trading interface; CEO login and audit trail; portable PostgreSQL migrations. Keep all trading disabled.

## Do — code built

- FastAPI `/v1/auth/login|me|logout`, `/v1/dashboard`, `/v1/students`, `/v1/students/{id}`, `/v1/students/{id}/direction`, `/v1/students/{id}/name`.
- Argon2 password hashing and interactive CEO bootstrapping. Signed eight-hour HttpOnly cookies, Origin checks, CSRF token for state-changing operations, basic in-memory login throttling.
- SQLAlchemy CEO/Student/LearningPlan/AuditEvent tables and Alembic initial migration for SQLite or PostgreSQL.
- React + TypeScript + Vite shell with authentic login, responsive navigation, student enrolment/plan editing/detail, activity-free dashboard and separately disabled Trading tabs.
- CI backend contract/migration tests and TypeScript/frontend build.

## Check

| Check | Status | Evidence |
|---|---|---|
| API contracts and regression | **Local PASS** | `python -m pytest backend/tests -q` — 23 tests |
| CEO-only student read/write | **Local PASS** | No cookie -> 401; missing/wrong CSRF -> 403 |
| Password & Origin protection | **Local PASS** | Incorrect credentials rejected; unauthorized origin denied |
| Unique student name | **Local PASS** | `Orion` and ` oRIoN ` collide, 409 |
| Persistence after restart | **Local PASS** | Second app instance reads same student ID from DB |
| Direction versioning | **Local PASS** | v1 directed, v2 autonomous; earlier market/skill targets preserved |
| Rename identity/history | **Local PASS** | UUID and v1 plan unchanged; collision 409 |
| Database migration | **Local PASS** | Clean SQLite upgrade to `0001_s1`, rerun idempotent |
| Disabled trading | **Local PASS** | No order/broker routes; capability flags false |
| Frontend strict TS build | **PENDING GITHUB CI** | npm registry inaccessible in local working container; verify in GitHub Actions |
| Mobile UX browser verification | **PENDING** | Responsive CSS authored; real browser rendering not yet audited |
| PostgreSQL migration integration | **PENDING HOSTED DATABASE** | Migration written but not yet executed against PostgreSQL instance |
| Public deployment | **NOT REQUESTED** | Must not publicly expose development API |

## Act / caveats

S1 is an **implemented foundation**, but cannot be called fully accepted until frontend build and browser UX checks pass. Since repository source is public, commit no credentials or financial account records.

Authentication is suitable for a localhost development milestone, **not public production** until HTTPS, a stable secret, persistent session revocation, multi-worker throttling, backups, audit policy, hardened infrastructure and a security review. PostgreSQL schema is prepared but its live database migration requires an approved hosted database. No CEO created in a deployed environment; initialise credentials interactively per README.

Next sprint after S1 acceptance: licence-backed XAUUSD ingestion with time-safe provenance and gap auditing.
