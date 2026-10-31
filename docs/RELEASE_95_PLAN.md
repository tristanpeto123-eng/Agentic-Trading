# Director milestone plan: 95% research-evaluation MVP

**Owner objective (31 October 2026):** Get Agentic Trading to 95% complete.
**Scope:** a reliable, independently testable **offline research-evaluation MVP**
with an iPhone CEO console. This is **not** 95% of a licensed, profitable or
paper/live trading business. No student may place broker orders under this plan.

## Definition of 95% and current state

The baseline is **13 of 20 individually verifiable acceptance gates = 65%**.
This is a conservative project-planning measure, not a scientific measure of
code completeness. A gate is accepted only when named evidence exists in a
versioned repository or an independently checked deployment. No fractional
credit for intentions, synthetic backtests or a green CI result alone.
**95% requires at least 19/20 gates, including all P0 blockers.**

| # | Acceptance gate | As of 31 Oct | Evidence / missing proof |
|---|---|---|---|
| 01 | CEO auth, access control and audit events | PASS | S1 API and security tests |
| 02 | Persistent student identities and plans | PASS | S1 student tests |
| 03 | Mobile-first CEO console | PASS | S1 mobile end-to-end tests |
| 04 | Historical data ingestion and quarantine | PASS | S2 import and provenance checks; not data certification |
| 05 | Deterministic conservative replay | PASS | S3 research fixture tests |
| 06 | Scout → Strategist → Guardian decision chain | PASS | S4 research tests |
| 07 | Immutable skills and closed-trade memories | PASS | S5 regression tests |
| 08 | Offline neural trainer and versioned checkpoints | PASS | S6 research tests, no alpha claim |
| 09 | Numeric independent Examiner prototype | PASS | S7 test suite, no Registrar |
| 10 | Recoverable Academy research queue | PASS | S8 test suite, fixture-only worker |
| 11 | Strategy DNA/peer lessons record | PASS | S9 research tests, no qualified evolution |
| 12 | Sentinel, durable stop and paper readiness blocked | PASS | S10–11 API guards |
| 13 | Authenticated read-only Alpaca preview and green research CI | PASS | S12A PR #26 and green 30 Oct CI; older Render SHA |
| 14 | Render revision equals approved repository SHA, security smoke passes | **OPEN P0** | Render deployed `d0b8c2b`; `main` at `991050b` on audit |
| 15 | Independently attested source provenance and usage rights | **OPEN P0** | Provider + acquisition/rights evidence unavailable |
| 16 | ≥12 months authentic XAUUSD M1 bid/ask (or independently accepted equivalent) | **OPEN P0** | No such independently validated execution tape |
| 17 | Frozen chronological holdouts, embargo and independently repeated walk-forward | **OPEN P0** | Code utilities exist; genuine evidence missing |
| 18 | Pinned model emits point-in-time signals; after-cost evaluation vs cash/no-trade | **OPEN P0** | No independent model→signal→Guardian→replay proof |
| 19 | Research policy update every five closed-trade batches with versioned rollback | **OPEN P0** | User-approved design; not qualified or automated end-to-end |
| 20 | Documented backup/restore, monitoring and release rollback drill | **OPEN P1** | Not demonstrated on hosted infrastructure |

**Current planning score:** 65% (13/20). **Goal:** 95% (at least 19/20).
Only #20 can be deferred at 95%; all P0 items are mandatory. A high
planning score does not qualify a strategy or unlock paper/live trading.

## Executable plan, in dependency order

### P0-A — Deployment parity and engineering hygiene (#14)
1. Run full backend, frontend, mobile and Render smoke CI on a named SHA.
2. Merge reviewed fail-closed changes only after checks pass.
3. Confirm Render's *actual deployed commit* equals the intended `main` SHA.
4. Recheck CEO login, Historical navigation, read-only Alpaca panel, all
   GET-only restrictions, safety latch, and denied paper order endpoints.
5. Store CI URLs, deployment ID, commit SHA and a dated verification note.

### P0-B — Genuine data, locked partitions (#15–17)
1. Obtain an owner-permitted provider export and a **separate, independently
   checkable** record of legal use, provider, acquisition method, instrument,
   timezone and bid/ask basis. Never commit purchased data or credentials.
2. Acquire sufficient verified history for chronological train/validation/test
   and forward walk-forward windows; M15 candles must not be marketed as
   fabricated M1 executions. An alternative to M1 must be independently
   approved with disclosed limitations.
3. Audit malformed/duplicate timestamps, extreme quotes, OHLC and volume,
   session gaps, spread, clock skew and missing trades. Store SHA-256 digests
   and a *private* rejected-row report.
4. Freeze partitions and configuration **before** model selection. Keep final
   unseen test data unavailable to learners and strategy selection.
5. Independently reproduce hashes and fold boundaries. No synthetic or
   quarantined data is eligible for promotion.

### P0-C — Genuine learning and evaluation (#18–19)
1. Pin the student identity, skill-catalog checksum, model version, market,
   feature schema, data digest and Guardian config to every research run.
2. Implement the user-approved policy-only update after **five batches of
   completed trades**. Skills remain frozen; update only an explicitly scoped
   student's selection/application policy. Record immutable before/after
   versions, inputs, validation results and rollback selection.
3. Only already closed, after-cost, TRAIN-partition episodes may teach. Data
   available after the decision timestamp must never leak into inference.
4. Evaluate a frozen model on unseen windows with realistic bid/ask spreads,
   commission, slippage, execution latency, stops/gaps and margin risks.
   Compare with a no-trade baseline and disclose all failed runs and trials.
5. Publish reproducible net P&L, trades, win rate, drawdown, expectancy,
   profit factor, confidence bounds, failed cases and multiple-trial policy.
6. Independent Examiner verifies that the **pinned model actually generated**
   the input signals. Numeric performance is not Registrar qualification.

### P1 — Operational release evidence (#20)
- Backups/restore and controlled migrations; worker resource ceilings.
- Stable secret/config rotation; paper account ID pinning and sanitised 401
  diagnosis, without disclosing credentials.
- Alerting, kill-switch and rollback exercises. Retest denied order routes.
- iPhone network/offline limitations and service restart/deployment recovery.

## Operating rules

- Existing issue [#18](https://github.com/tristanpeto123-eng/Agentic-Trading/issues/18)
  remains the canonical cross-workstream gate. Link accepted PRs, test runs,
  signed provenance and deployment checks to the issue.
- Render **Free** may reset local storage; temporary imports are not durable
  training evidence. Use approved persistent storage before qualification.
- An owner request to reach 95% is **not** a separate approval to place paper
  or live orders, engage a broker execution route or promote a model.
- A successful Alpaca GET-only snapshot confirms only read-only paper API
  visibility; it does not prove strategy profitability.
- Gates #15–18 depend on actual external data/evidence and cannot be completed
  by invented observations, synthetic fixtures, changing source labels or
  improving a percentage dashboard.
