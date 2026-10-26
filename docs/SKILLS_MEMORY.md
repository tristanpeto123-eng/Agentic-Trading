# Sprint 5 — Student skills and episodic trade memory

## Scope

**Implemented:** immutable versioned code-owned skill catalogue (`/v1/skills/catalog`), a student-linked closed-trade research archive, costs-derived Good / Bad / Flat outcomes, SQL-backed append-only/idempotent internal ingestion, bounded time-safe recall, per-skill descriptive statistics, read-only CEO endpoints, mobile-first Student Skills and Memory tabs, and Alembic schema revision `0003_s5`.

**Not implemented:** autonomous episode creation, automatic training, neural weight updates, skill teaching, consolidation or transfer, independently examined skill mastery, promotion, broker connections or order execution.

**Safety:** During S5, episodes can only be `synthetic_fixture` or `historical_quarantined` (with source hash matched to a known quarantined dataset). All are research-unqualified. The API offers **no endpoint to create, edit, delete or approve episodes**. The internal importer is callable only by trusted Python research workers; callers are responsible for passing actual simulator source outcomes rather than user-supplied claims.

## Versioned Skill Library

Each market (e.g., `market:XAUUSD`) and trading tactic (e.g., `tactic:trend`) is a separately versioned entry with prerequisites. Tactics currently require `risk:risk_management`. A stable `catalog_sha256` traces the immutable catalogue used by a particular training package. Learning-plan targets remain distinct from **earned**, independent qualifications. An `unassessed` mastery status does **not** imply skill competence, even after many archived wins.

## Closed-trade evidence contract

Each record includes a unique event UUID and student UUID, strategy version, proposal hash, source ID/hash, partition (`train`, `validation`, `holdout`), UTC signal/open/close/availability times, instrument, market regime, skill IDs, positive starting risk, gross USD P&L, spread/slippage/commission costs, MFE and MAE in R, and a closing reason.

- `net_pnl_usd = gross_pnl_usd - spread_cost_usd - slippage_cost_usd - fees_usd`
- `net_r = net_pnl_usd / initial_risk_usd`
- `good` if `net_pnl_usd > 0`, `bad` if `< 0`, otherwise `flat`

Never infer win/loss from price direction, gross P&L, accuracy, or self-reported labels. A profitable gross trade can still be a `bad` trade after costs.

The content hash covers the canonical full payload, and denormalized indexes are checked against it on read. Exactly repeated event IDs with identical content are idempotent; conflicting attempts fail closed. SQLite/PostgreSQL privileged DB administrators could still modify data directly, so SQL/database-level append-only permissions and signed external evidence are further hardening work, not a present guarantee.

## Time-safe recall and separation

The Recall Engine accepts an explicit UTC `as_of` timestamp. It returns **only closed, available, training-partition episodes** belonging to the specified student. Optional skill, market, regime and excluded-source filters narrow matching. It never retrieves validation/holdout outcomes or episodes where `available_at > as_of`. The CEO API also seals validation/holdout episodes from both the archive display and skill-statistics calculations until a future independent Examiner explicitly releases those results. All archive reads check stored payload integrity and fail closed on mismatches.

**Important limitations:** Data partition membership is currently a trusted internal research-worker assignment; independent immutable partition manifests and embargo/purging checks belong to S7. Long-lived training workers and full memory consolidation are S6/S8. S5 cannot validate that archived gross P&L was produced by a genuine, independently reproducible market replay; provenance checks ensure correct matching to S2 source metadata only. No training or qualification relies on S5 data until the independent data and Examiner gates pass.

## CEO API (read only)

- `GET /v1/skills/catalog` — versioned skills, prerequisites, catalogue hash.
- `GET /v1/students/{student_id}/skills` — targets and archive statistics, **mastery always `unassessed`**.
- `GET /v1/students/{student_id}/memory?limit=50` — recent **training-partition** episodes with after-cost outcome/magnitude and explicit research-only provenance. Limit range 1–100.

Existing CEO cookie authentication and CSRF controls remain unchanged. No memory-write route is mounted.

## Acceptance criteria

1. A closed episode derives Good/Bad/Flat from net financial magnitude after explicitly itemized costs.
2. A non-UTC, future-visible, non-closed or nonsensical episode is rejected.
3. Only catalogued market/tactic skills with prerequisites are accepted.
4. Synthetic and quarantined sources cannot become independently qualified.
5. Duplicate writes are idempotent; conflicting UUID or tampered content fails closed.
6. Recall cannot see future, other-student, validation or holdout outcomes.
7. Student history remains after learning-direction changes and database restarts.
8. Skills and Memory screens show real archive data or honest empty states without claiming mastery.
9. Full S0–S4 regression suite and migration test pass.
10. GitHub backend, frontend TypeScript build and mobile-browser CI pass before merging.

See `docs/SPRINT5_CHECK.md` for recorded checks and open gates.
