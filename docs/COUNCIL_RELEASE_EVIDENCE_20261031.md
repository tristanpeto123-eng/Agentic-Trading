# Council research-release evidence — 31 October 2026

**Scope:** Research tooling and evidence collection only. Not a qualified trading release. Issue #18 remains the canonical cross-workstream gate.

## Deployment and operations verification

- Main repository commit inspected: e0a232d9463ebcd5f5ce44be67784ec0c2577418.
- Render service agentic-trading-iphone-preview-2026 most recent **live** deploy dep-dbj43be7bikc73ec64qg reported that SHA at 19:31 UTC. This verifies revision parity at that checkpoint. Any later merge requires a fresh comparison.
- Main SHA action runs: research verification [41233771406](https://github.com/tristanpeto123-eng/Agentic-Trading/actions/runs/41233771406), preview smoke [41233771387](https://github.com/tristanpeto123-eng/Agentic-Trading/actions/runs/41233771387), Pages [41233771228](https://github.com/tristanpeto123-eng/Agentic-Trading/actions/runs/41233771228): all reported success. Preview smoke occurred *before* the later Render deploy; neither proves authenticated end-to-end checks on that deployed revision.
- Ephemeral PostgreSQL dump/migration/restore CI exists and has passed; it does not prove an actual hosted restore, persistent backup or DR objective.
- Render free PostgreSQL is scheduled to expire on **25 November 2026**. Hosted retention/restore remains a blocker. Do not widen private database access for convenience.
- Paper/live order routes remain unavailable; read-only Alpaca visibility does not grant execution authority.

## Owner-supplied XAUUSD archive audit

Private structural audit performed on available library CSVs. Raw quotes and original local file paths were NOT committed.

| Data | Observed structural result | Assessment |
| --- | --- | --- |
| 28 Oct 2026 M1 BID/ASK | 1,267 matched minute timestamps, two BID-only; all matched close-spread proxies positive, median USD 0.554/oz | One-day structural sample only; no source/rights or executable-tick attestation |
| 29 Oct 2025–23 Oct 2026 M15 OHLC | 23,416 rows, ~360 calendar days, 327 gaps requiring session-calendar review | Format check only; provenance and >=365-day requirement not established; no M1/tick fills |
| 1–28 Oct 2026 H4 BID | 119 rows, ~28 days | Supplemental context only |

Do not assume calendar gaps equal missing trading-session quotes without the provider calendar. Two M1 ASK files were byte-for-byte identical; no extra history resulted.

Data supplier: An FXCM Pro bid/ask licensing enquiry was sent 31 October; no supplier response located by this review. No data purchase/redistribution authorised.

## New reproducible offline fold utility

Run privately on an authorised original CSV:

    python scripts/freeze_research_folds.py /private/xauusd_15m.csv --minutes 15 --embargo 96 --folds 3 --output /private/frozen_folds.json

The script checks UTC timestamp order/alignment, OHLC bounds and optional volume, rejecting malformed/duplicate/reversed rows and insufficient folds. It hashes original bytes; creates deterministic 60/20/20 train/development-validation/final-test boundaries with two-sided embargo; and three expanding walk-forward development folds *inside training only*. It exports final holdout boundary metadata but not prices, and cannot contact a broker.

**A manifest does not enforce independent data isolation.** A research runner still needs actual access control, pinned model/skill/data/config hashes, point-in-time signals, and independent after-cost replay on genuine unseen market periods. Embargo must cover the actual maximum label and feature horizon; 96 bars is configurable, not certified.

Source legitimacy, rights, model-level isolation, independent examination, and paper/live eligibility are explicitly FALSE in the emitted report.

## Gate disposition

- Deployment SHA parity: verified at checkpoint; final authenticated hosted-release checks pending.
- Source licence/provenance: BLOCKED.
- Execution-grade history: BLOCKED (only ~one-day M1 pair available).
- Chronological fold generator: IMPLEMENTED and tested on sample; model isolation and walk-forward results remain BLOCKED.
- Pinned-model after-cost independent examination: BLOCKED (no reproducible qualified performance).
- Operational release: PARTIAL (ephemeral CI recovery is not hosted restore evidence).
- CEO trading activation: not requested or authorised; trading locks remain engaged.

Next: independently documented data rights and sufficient execution quotes; actual model-to-Guardian-to-replay unseen runs and examiner review; hosted backup/restore and exact-version authenticated smoke; then separate owner release approval. Do not adjust the milestone percentage based only on newly documented tests.
