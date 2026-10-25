# Sprint 0 — Checker Report

**Date:** 2026-10-25
**Scope:** Contract and development scaffold only. No working trading system has been delivered.

## PLAN

Implement a separate Agentic Trading foundation based on `PRODUCT_SPEC_v1.0.md`. Keep live, paper and historical execution disabled until appropriate sprints. Preserve approved CEO governance.

## DO — artifacts completed

- Independent Python package (FastAPI local read-only API).
- Contract models: `EventEnvelope`, `Provenance`, `TradeProposal`, `TradeAssessment`, `GuardianDecision`, `CEOApproval`, `ResearchExamEvidence`.
- Pure policy checks: proposal revision binding, Guardian veto, CEO scope check, promotion numeric/evidence gate.
- Versioned JSON schema exports for future frontend consumers.
- Automated pytest suite and GitHub Actions workflow configuration.
- Three-tab UX wireframes, provider shortlist, security instructions and ADR.
- Local Git commit / downloadable repository scaffold.

## CHECK — verified in container

| Acceptance check | Result | Evidence |
|---|---|---|
| Python tests and contract snapshots | **PASS** | 14 tests, `python -m pytest backend/tests -q` |
| Code compiles | **PASS** | `python -m compileall -q backend/src` |
| Package locally installable offline | **PASS** | `pip install --no-build-isolation --no-deps -e ./backend` with locally installed build tools |
| Real local HTTP startup | **PASS** | Uvicorn on localhost, `GET /health` => HTTP 200 |
| Operational capabilities fail-safe disabled | **PASS** | `/v1/capabilities`: historical/paper/live execution and student creation false |
| No broker trade endpoints | **PASS** | POST `/v1/orders`, `/v1/broker/connect` => 404 (test) |
| Synthetic exam promotion rejected | **PASS** | Unit policy tests |
| Guardian denial/absence blocks research intent | **PASS** | Unit policy tests |
| Proposal revision invalidates prior score/Guardian | **PASS** | Unit policy tests |
| CEO approval exact instrument/account/model/time | **PASS** | Unit policy tests, schema only — not authentication |
| GitHub repository exists | **PASS** | Owner created `tristanpeto123-eng/Agentic-Trading` as a **public** repository. |
| Remote scaffold published and CI passing | **PASS** | Initial public GitHub scaffold and 14-test workflow were reported verified in Sprint 0 delivery. |
| React site & user login | **NOT IN S0** | Scheduled for Sprint 1 |
| Real market data, models and trading | **NOT IN S0** | Later sprints; no performance claims |

## REVIEW FINDINGS & LIMITATIONS

1. **Public GitHub repository selected by CEO**. Keep secrets, broker credentials, account details, private data and local environment files out of git. Publishing source code does **not** mean deploying the unauthenticated API publicly.
2. **No authenticated CEO endpoint yet**. `CEOApproval` is a schema, not proof that the actor signed in; real authority must be enforced server-side using persistent approved records, immutable audit and account binding in later sprints.
3. **Provenance is structured but not yet independently verified.** Registrar must cross-check candidate data against authoritative dataset manifests and protected holdout identifiers before promotion. The current `can_promote_research` is a necessary-condition function, not a final promotion service.
4. **No licensed XAUUSD provider chosen**. S2 remains blocked on rights/data completeness verification.
5. API has **no user authentication**. Bind to localhost only; do not deploy or expose it publicly until Sprint 1 security checks pass.

## ACT — next actions

- Publish Sprint 0 scaffold to the new **public** `Agentic-Trading` repository. Verify remote files and GitHub Actions checks.
- Then proceed to S1: React shell, authenticated CEO role, PostgreSQL-backed student identity + names, automatic/directed learning-plan versioning.
- Keep all trade execution disabled, preserve champion and immutable evidence rules.

**Verdict:** Sprint 0 foundation complete; Sprint 1 began with a confirmed public GitHub repository.
