# XAU/USD historical data acquisition — 14 November 2026

The owner requested a data source and directed that licensing review be omitted.
Acquired the public [Market Data Lab archive](https://github.com/kevingtlin/Market-Data-Lab)
at pinned commit `b60bd71d0e34a42cb962daf688ff252e73f409ca`:
24 monthly BID/ASK M1 CSVs for January–December 2025, 52,555,216 raw bytes.
Each raw file matches its pinned Git blob digest; private manifests retain
SHA-256 hashes and exact retrieval metadata.

Private dataset and reproducible preparation scripts:
`/workspace/agentic-private-data/market-data-lab-2025/`.
No downloaded prices or private manifests are committed to this repository.

## Observations

| Check | Observed result |
|---|---|
| Aligned raw M1 timestamp pairs | 525,600 |
| Ordered UTC timestamps and valid positive OHLC | PASS |
| Conservative quality exclusions | 176,217 pairs |
| Remaining screened M1 pairs | 349,383 |
| Complete screened M15 windows | 23,276 per side |
| Incomplete M15 groups omitted | 18 per side |
| App CSV import validation | PASS for both M15 files |
| Preserved M15 gap events | 257 per side |
| Chronological folds | Created with 96 M15 bars embargo |
| Fixed-skill pipeline smoke | Completed; `research_failed`, flat/no-trade selected |

The archive includes unchanged prices during closures. Screening excludes
bid-and-ask runs unchanged for at least 30 minutes and UTC weekends, with
overlapping exclusion counts recorded privately. This conservative rule also
omits genuine Sunday opening quotes. No missing price is generated, and the
raw originals remain intact. Screening is retrospective, not point-in-time
verification of a provider session calendar.

The screened M15 files cover 363.9479 calendar days; the import parser correctly
leaves its 365-day coverage target open. Source documentation describes
Dukascopy origin via dukascopy-node, but this is a third-party archive, not
independently attested direct provider delivery. M1 candle aggregates do not
establish executable simultaneous tick quotes.

The exploratory integration used an explicit 1,380-minute contiguous screened
segment (whole-year files retain gaps), two generations/ten batches, assumed
round-trip fee 0.05 and per-side slippage 0.20 per unit. All three numerical
test windows had zero trades and failed their minimum-trade/profit gates.
This confirms data flow, not useful performance or independent qualification.

Initial alternatives: Dukascopy direct archive requests returned HTTP 503/429;
FXCM XAUUSD sample URLs returned 404. No credentials, purchases or provider
access-control changes were used. Licensing is recorded as unverified, without
holding up this acquisition. Model promotion and trading remain disabled.
