# Sprint 4 — Checker: Trading Intelligence (PDCA)

**State: deterministic research baseline built locally; proposed for PR review. This sprint does not grant model qualifications.**

## Plan
Create an offline, point-in-time, inspectable and fail-closed Scout A / Strategist B / Scout B / Guardian A pipeline compatible with S3's conservative M1 replay, without exposure to paper/live modes. Explicitly distinguish baselines from neural models.

## Do
- Immutable typed candle window, UTC / continuity / completed-bar guards, deterministic source/decision fingerprints.
- Multi-axis market regime state (trend/range/chop/uncertain and compressed/normal/high/extreme) using completed H1/H4 checks.
- Tactic-specific candidate proposals (trend/breakout/range) with stops, targets, thesis, version and expiry.
- Scout B conditional mean net R from prior closed training records; strict point-in-time training cutoff, distinct source hash and minimum bucket evidence.
- Strategic final abstention on nonpositive expected R; mandatory Guardian veto with conservative research-only position sizing.
- Guardian A thesis observations without autonomous interventions.
- Optional synthetic-only handoff into S3's historical replay; no API or execution endpoints.

## Check
- **76 backend regression/scenario tests passed locally** (`PYTHONPATH=backend/src python -m pytest backend/tests -q`) prior to GitHub push. CI must be rechecked after publication.
- New scenarios exercise upward/downward trend, breakout, range, H1/H4, insufficient data, gaps, invalid timestamps, closed-training-only, source overlap, proposal/trace tampering, altered revision, Guardian veto, synthetic replay and qualification prohibition.
- Stable outputs on identical immutable inputs; no fabricated trained neural model, profitability rate or verified source rights.
- CEO governance invariant: source code has no broker adapter, no enable-paper/live endpoint, no qualification promotion.

## Act / outstanding gates
- **S2**: verify genuine licensed XAUUSD history, provenance, coverage, partition manifest and independently approved data source. Existing provider files remain quarantined.
- **S3**: broker-like execution realism, known bid/ask quotes at M1 or finer frequency, costs, session/swap and partial-fill stress.
- **S6/S7**: data-safe trained ML scouts, strict walk-forward and independent Examiner/Registrar. Current deterministic empirical baseline cannot auto-promote itself.
- GitHub CI, independent code review and explicit owner approval required before merging S4. Parent branch is S3, which is based on unmerged S2.
