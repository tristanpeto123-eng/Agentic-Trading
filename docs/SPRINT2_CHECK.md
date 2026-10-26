# Sprint 2 — Data Engine (Checker / PDCA)

**Status: ENGINEERING VALIDATION COMPLETE; PROVIDER EVIDENCE GATE OPEN.**

## Plan
Implement a research-only, immutable XAUUSD historical M15 import path, UTC timestamp quality checks, reproducible frozen source/canonical files, manifest hashes, gap/malformed/duplicate reports and point-in-time M15/H1/H4 context. The research-validation gate must never mistake local examples or undocumented files for independently verified real market data.

## Do
- CEO-only `GET /v1/datasets`, `POST /v1/datasets/import`, `GET /v1/datasets/{id}`, `GET /v1/datasets/{id}/context?as_of=<UTC ISO timestamp>` with signed-cookie auth and CSRF on import.
- CSV `timestamp_open,open,high,low,close[,volume]` (UTC only), strict increasing M15 rows, time alignment, OHLC sanity, finite positive prices, nonnegative optional volume, closed-at-acquisition, max 80,000 bars / 12 MiB.
- Immutable content-addressed raw CSV + deterministic normalized M15 JSONL. SHA-256 of both files, verified on every context read. Provider, source, extraction reference, price basis, rights reference, acquisition timestamp, evidence kind saved in durable database metadata.
- Missing intervals reported, never fabricated; weekend timestamps, suspicious price jumps, long flat streaks and short historical coverage warned. `research_eligible=false` regardless of format correctness until independently verified source rights and real-world provenance.
- Completed-only H1/H4 aggregates at a caller-provided historical `as_of`, with no incomplete higher timeframe exposure. No feed, training, broker or execution endpoints.
- Nested Home → Data Engine form; no extra primary navigation tab. SQLite/PostgreSQL Alembic revision `0002_s2`.

## Check

| Gate | Outcome |
|---|---|
| S1 authentication, student records and safety regression | Local pytest PASS |
| Strict OHLC, UTC and time alignment | Local pytest PASS |
| Detect malformed, duplicate, negative, nonfinite, future candles | Local pytest PASS |
| Detect gaps without interpolation | Local pytest PASS |
| H1/H4 only after full M15 window closes | Local pytest PASS |
| Quarantine all CSV sources; research/trading remain disabled | Local pytest PASS |
| Duplicate raw import idempotent; conflicting provenance rejected | Local pytest PASS |
| Persistent metadata + immutable storage + tamper rejection | Local pytest PASS |
| Database upgrade with `0002_s2` | Local pytest PASS |
| GitHub frontend build and mobile tests | To verify in Sprint 2 PR CI |
| >=12 months **genuine licensed** XAUUSD + completed provider audit | **BLOCKED: NO PROVIDER/DATA/RIGHTS VERIFIED** |
| M1/tick or broker bid/ask execution evidence | Pending later data extension / Sprint 3 |

## Act
Do not mark S2's external-data acceptance criteria complete without independent provider and rights checks and a licensed 12-month XAUUSD M15 export. Synthetic fixture data may test parsers and continuity but is not financial evidence. Import states are quarantined; there is no source qualification route, trading model training, or financial result. No user credentials or raw licensed market data should enter the **public** GitHub repository.

## Source provider decision gate
Choose MT5/OANDA/Dukascopy or another provider only after verifying instrument availability, usage licence, UTC encoding, price basis and whether bid/ask and lower timeframes are available. Broker-dependent executable spreads/slippage are still S3 requirements. Do not label midpoint candles as executable prices.

## Follow-up: direct provider research adapter

- Added `agentic_trading.providers.dukascopy` and opt-in `scripts/fetch_dukascopy_xauusd.py`
  for bounded direct historical data retrieval or offline conversion of cached `.bi5`
  M1 BID/ASK files to immutable, UTC M15 bid/ask-separated CSV exports.
- Added decoder, incomplete-bar, corruption, duplicate, input-bound, crossed-quote,
  cache verification and zero-network tests. Strict 12-month licensed source
  verification remains pending; no actual provider dataset has been retrieved here.
- The public GitHub repository contains source code and tests **only**, not raw
  Dukascopy data, credentials or redistributable price histories.
