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
