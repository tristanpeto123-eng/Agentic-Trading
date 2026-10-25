# Sprint 4 — Offline Trading Intelligence (reference policies)

**Classification: research-only baseline. No trained neural network, real profitability, paper/live trading, broker connection or student qualification.** S2 licence/source and S3 execution realism gates remain open.

## Decision order

1. **Scout A** analyses the latest **completed**, contiguous XAUUSD M15 bars and independent volatility/directionality axes. It uses rolling true range, efficiency ratio, completed H1/H4 closes and conservative abstention for insufficient history, higher-timeframe conflicts, chop and extreme volatility. The first implementation is a **deterministic rules baseline**, not a trained regime classifier. `MarketWindow` forbids unfinished/future candle windows; `source_sha256` is an unverified claim unless validated by the external data provenance system.
2. **Strategist B (candidate)** emits deterministic LONG/SHORT trend continuation, breakout or range-reversion candidates with explicit stop, target, thesis, expiry, price reference, revision and content digest. It abstains on unsuitable regimes/volatility. The candidate is **not** an order.
3. **Scout B (baseline)** estimates conditional *realised net R* from previously **closed** training samples matched by tactic, regime and evidence type. Training cutoff must be strictly before the beginning of the evaluation window, source hashes cannot be reused, and buckets need at least 12 independent sample IDs. It is not a trained MLP, a calibrated predictive probability, or a verified edge. A positive sample average is not proof of future profit.
4. **Strategist B (final)** abstains if model/data are missing or expected net R is below policy. Changing any proposal field requires a new content digest, assessment and Guardian review.
5. **Guardian (mandatory)** checks proposal/assessment binding, timestamps, regime confidence, expected net R, loss budget, position size and leverage. It returns an auditable APPROVED/DENIED *historical research intent*; it never creates paper/live authorisation. True live spread can only be checked against M1 bid/ask quotes during replay; M15 mid-price inference cannot verify executable spread.
6. **Guardian thesis monitor A** emits VALID, WEAKENING, INVALIDATED or UNCERTAIN *observations only*; it has no exit or order authority.
7. **Historical simulator integration** converts only a valid Guardian-approved research trace into an S3 historical order. The execution tape must start after the decision time and carry a distinct M1 source-artifact SHA-256; signal and execution source hashes are never conflated. An unresolved trade remains unresolved, and all results are non-qualifying, even if the caller self-labels the dataset verified.

## Data/time requirements

- M15 candle `open_time + 15 minutes == available_at`; UTC, strict chronology, contiguous recent window. No synthetic candles, filling gaps, sorting, or backdating.
- H1/H4 comparisons use **full completed periods only**. Incomplete higher-timeframe periods are omitted. No future bar is consumed.
- Scout B samples have immutable IDs and close timestamps before the frozen training cutoff. The provenance system must later certify data rights, independence and non-overlapping train/test partitions; matching asserted hashes alone is not sufficient.
- Each decision has a stable trace hash and separate immutable proposal/assessment/Guardian hashes. Malformed or modified payloads fail closed in the research replay path.
- Quote-level risk/fill modelling belongs to S3, independent examinations to S7, neural learning and checkpoints to S6. None are silently simulated by S4.

## Local demonstration

`PYTHONPATH=backend/src python scripts/demo_research_intelligence.py`

Only synthetic test candles and synthetic historical net-R samples are used. Inspect `backend/tests/test_intelligence.py` for scenario coverage. Do not use the demonstration's trade results in strategy selection or marketing.

## Known limitations / further sprint acceptance gates

- No API/dashboard interface for model operation and no persistent runs yet; intentional separation from CEO access and trading permissions.
- One XAUUSD instrument; 15-minute research decisions, completed H1/H4, optionally executed using pre-existing M1 bid/ask replay.
- Scout A/B are transparent reference baselines; **no claim of ML training**. Real forecasting calibration, stress tests, walk-forward and teacher-driven learning are future work.
- Range/trend thresholds and cost assumptions are provisional—not optimised against verified outcomes.
- Comparison of multiple simultaneous proposed positions and aggregated portfolio exposure will require explicit Guardian portfolio state before paper/live.
- Historical replay still lacks verified source rights, production spread/quote availability, swaps, partial fills, broker venue realities and independent qualification.
