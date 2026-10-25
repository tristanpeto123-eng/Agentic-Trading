# Design Decisions (approved baseline + sprint-gated choices)

| ID | Decision | Status |
|---|---|---|
| D-001 | Project name **Agentic Trading**, independent of all Scalp City repositories, software and data | Approved |
| D-002 | Three navigation tabs: Home, Students, Trading; settings contextual | Approved |
| D-003 | Named student identity with CEO-Directed or Autonomous learning, editable versioned curriculum | Approved |
| D-004 | Skills include markets and trading techniques; memory associates experiences with skills | Approved |
| D-005 | Automatic research and research promotion; exact-scope CEO approval for paper activation/live actions | **Locked** |
| D-006 | No live capabilities in research MVP; observed Guardian A cannot auto-exit from ML verdict | Approved |
| D-007 | Research outcomes require net profitability after costs, independent examination and data integrity | Approved |
| D-008 | FastAPI + React/TypeScript + PostgreSQL + PyTorch + object storage | Proposed stack approved as build baseline |
| D-009 | Initial XAUUSD market provider with adequate licence and execution evidence | **Open — S2 gate** |
| D-010 | Hosted job queue, hosting provider and secret-management infrastructure | **Open — S1 gate** |
| D-011 | Exact CEO financial risk limits and paper/live broker choice | **Open — before activation** |
| D-012 | Plain-English student briefings, Skill Mastery, DNA/evolution, controlled peer teaching and mentorship | Approved design |

## Approval requirement

No autonomous research component or UI may authorize capital allocation, live deployment, increases of risk or leverage, a live model swap, new live instruments or reactivation after safety suspension. Research champion status does not confer trading permission.

## Repository visibility

The CEO elected to keep the independent Agentic Trading GitHub repository **public** (2026-10-25). Do not commit secrets, tokens, broker/account credentials, private user records, or real trading datasets. Sprint 1 adds CEO authentication and server-verified permissions. Deployments still require HTTPS, stable secrets, durable DB, distributed login throttling and operator security approval.

## Sprint 1 choices

- D-013: Research-phase student records use immutable UUID identity and SQLite in local development; Alembic migrations target PostgreSQL for hosted operation.
- D-014: CEO login is bootstrapped interactively with an Argon2-hashed password; signed HttpOnly eight-hour cookies and CSRF protect authenticated writes. Sessions are development-grade until production secret management, persistent revocation, audit/access review and multi-worker throttling are implemented.
- D-015: Both learning modes persist as plans; student creation does **not** begin training, grant skills or qualify trading. No simulated balance/P&L will be fabricated in the UI.
- D-016: Public repository is **source visibility only**; frontend and API are not deployed. No GitHub source push constitutes live or paper trading approval.
