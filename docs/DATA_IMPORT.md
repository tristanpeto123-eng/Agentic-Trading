# Data Engine — S2 Operator Guide

The application can now **ingest a real XAUUSD M15 CSV supplied by the CEO**. It cannot independently guarantee the export came from the named provider. All imports are quarantined, never independently research-qualified.

## CSV shape

```csv
timestamp_open,open,high,low,close,volume
2025-04-07T00:00:00Z,3020.1,3022.0,3019.4,3021.8,123
2025-04-07T00:15:00Z,3021.8,3023.2,3020.5,3021.4,115
```

**Example values above are invented, not real market data.** Volume is optional. Timestamps must be offset-aware UTC opens of completed M15 bars, aligned to a quarter hour. Every row must be strictly later than the previous. For now one file maxes out at 12 MiB and 80,000 rows. The raw transfer is kept unchanged; canonical prices are decimal strings. Gaps are visible, not filled. Weekend/session gaps require interpretation using the *actual* provider calendar before qualification.

## Workflow
1. Get an original licensed export and record the provider name, HTTPS source reference, export command or reference, rights document reference and whether prices represent bid/ask/mid/trade. Check instrument XAUUSD, at least 12 months requested, and UTC timeframe M15.
2. Sign in to the locally running CEO console. Open Home → Data Engine → Import CSV and provide the data and provenance metadata. Import is authenticated with CSRF.
3. Review the persistent dataset quality record and SHA-256 hashes. The API can query historical completed M15/H1/H4 bars by `as_of` timestamp. No historical future bars are returned. Context reads rehash both artifact files.
4. **Do not train or trade.** External source authenticity, licensing and data coverage must be independently checked, and the provider approval mechanism intentionally does not exist yet.

## Storage and security
Set `DATA_STORAGE_DIR` to a **private durable disk** separate from the GitHub checkout, alongside a backed-up `DATABASE_URL`. The default local directory `data_store/` is ignored by Git. Raw prices and personal/provider account metadata may be subject to redistribution restrictions; never commit the CSV, database, tokens or provider exports to this public repository. Static read-only context is currently synchronous and not intended as a high-throughput training data interface.

## Missing capabilities
A verified vendor-specific API, source licence evidence review, 365-day/market-session certification, bid/ask spread modelling, M1/tick replay, Parquet partitioning, partial dataset stitching with overlap handling, stale-data cancellation and scheduled ingestion are not complete. Future sprint gates must distinguish structural validity, provider authenticity and economic execution realism.

## Optional direct-source adapter: Dukascopy XAUUSD M1 BID + ASK (research only)

Dukascopy publishes historical prices through its JForex historical-data tools and its
public `.bi5` datafeed. The adapter is **an independently written reader** of that
format, not a licensed official client and **does not verify your reuse rights**.
Its public endpoint format is subject to provider changes. If terms or usage rights
are uncertain, use Dukascopy's own JForex export process or a licensed broker export.
Raw quote prices cannot be assumed identical to your intended live broker's fills.

Offline mode is default; place `.bi5` files under `data/dukascopy-cache/` yourself
or explicitly enable HTTP fetching. The source cache and output are gitignored.

```bash
python -m pip install -e './backend[dev]'
# A small test range first. Dates are UTC, end-exclusive, never more than 400 days.
python scripts/fetch_dukascopy_xauusd.py \
  --from-date 2025-10-20 --to-date 2025-10-24 \
  --cache-dir data/dukascopy-cache --out-dir data/exports --download

# Full period example; **not pre-fetched or qualified by this project**.
python scripts/fetch_dukascopy_xauusd.py \
  --from-date 2025-10-01 --to-date 2026-10-01 \
  --cache-dir data/dukascopy-cache --out-dir data/exports --download
```

The exporter retrieves M1 BID and ASK candles separately, preserving original
compressed files and their SHA-256 provenance, and emits one **UTC M15** CSV per
side plus `dukascopy_provenance.json`. It **drops** any M15 period missing one
of its 15 minute observations, with omissions explicitly reported. It does not
impute prices, automatically assume missing files are market closures, or claim
that quote volume represents exchange-traded volume. Oversized, malformed,
duplicate, implausibly priced or corrupted files fail closed. Every cache entry
is verified on read and provenance records track fetch URLs and raw hashes.

Import each M15 CSV under Home → Data Engine and set `price_basis` to the matching
BID or ASK side. Set `provider` to `Dukascopy`, record the source URL as
`https://datafeed.dukascopy.com/datafeed/`, the script/date range plus
`dukascopy_provenance.json` in `extraction_reference`, and a genuine terms/permission
reference in `rights_reference` (not an invented one). The provider/rights field is
not a licence certification; **all imports remain quarantined**.

The provider download cannot run from this development container because its
network is inaccessible. No real file has been fetched or admitted to research.
Before lifting the gate: review your rights, verify original source authenticity,
confirm BID/ASK agreement and expected market sessions, inspect coverage/omitted
minutes and source 404s, verify all hashes, and independently test dataset
quality. Trading and training remain disabled.
