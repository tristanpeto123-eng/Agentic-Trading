# ATL dual-source XAU/USD BID/ASK research feed

## What this adds

The existing **Train a student** workflow can acquire paired XAU/USD BID and ASK M15 bars from either:

1. **OANDA v20 practice** — authenticated GET to `https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles` with `price=BA`, `granularity=M15`, `count=2016` and `smooth=false`; never a live or order endpoint.
2. **Dukascopy** — the existing, bounded weekday M1 BID/ASK `.bi5` collection, matched and aggregated into **complete** paired M15 candles. No OHLC rows are fabricated for missing minutes.

Both return the same schema:

```json
{
  "open_time": "2026-10-01T00:00:00Z",
  "available_at": "2026-10-01T00:15:00Z",
  "open": "3000.2",
  "high": "3001.2",
  "low": "2999.2",
  "close": "3000.4",
  "volume": "42",
  "bid": {"open":"3000", "high":"3001", "low":"2999", "close":"3000.2"},
  "ask": {"open":"3000.4", "high":"3001.4", "low":"2999.4", "close":"3000.6"}
}
```

**This example contains invented prices**. The scalar OHLC is an unsynchronised average of side-specific OHLC used for training *features*, **not tradable mid candles**. Replay economics use ASK open / BID close for longs and BID open / ASK close for shorts. There is no slippage, funding, commission or actual fill record. Training results remain hypothetical.

Each response provides a deterministic canonical SHA-256, UTC available-at timestamps, gap count, source/provider, provenance where applicable and explicit `source_verified=false`. Missing, incomplete, future, duplicated, reversed, crossed or malformed records fail closed. OANDA incomplete candles are dropped; every paired Dukascopy M15 bar requires 15 observed individual M1 quotes per side.

## Private deployment configuration

Set the following only in the **backend** environment, such as your private Render/Railway service, never in the frontend or GitHub source:

```env
OANDA_V20_PRACTICE_TOKEN=<your private OANDA v20 practice token>
ATL_OANDA_PRACTICE_RESEARCH=1
ATL_DUKASCOPY_RESEARCH_DOWNLOAD=1
ATL_XAU_CROSSCHECK=1
DATA_STORAGE_DIR=/private/durable/data_store
```

These flags default to **0**. Enable a provider only after reviewing its data-use terms, storage and automated retrieval conditions, and any private ML-training restrictions. The app cannot infer permission from a valid account token or accessible URL. Set `ATL_XAU_CROSSCHECK=1` only when both feeds are configured; it compares same-timestamp close midpoints without mixing prices. Discrepancy figures are informational, not independent certification.

The preferred source is OANDA practice if configured and valid, then Dukascopy. Existing archived XAUUSD M15 data remains a fallback. For autonomous students, BTC/USD research may also be selected using the existing path. The interface still needs only **choose student → Train**; provider choice is not a new mandatory button. OANDA setup is **not** the same as Alpaca paper credentials.

Dukascopy can require multiple sequential historical HTTP downloads on a cold cache (up to 20 files for 10 weekdays). A durable private cache is advised. It is not safe to deploy vendor data files or tokens into a public repo. Cache files carry source hashes and are never intentionally committed.

## Intentional restrictions

- Both feeds are read-only research; **no account orders**, no paper execution, no live orders and no model qualification.
- OANDA supports bid/ask candle **aggregates**, not historical timestamp-synchronised trades. Dukascopy M1 side candles are likewise not executable tick records.
- The model uses historical mid-based features and can save research neural weights via the **existing** neural training mechanism; displayed policy-replay P&L is a separate hypothetical exercise.
- No licence approval, source authenticity check, independent model validation, out-of-sample qualification or capital allocation approval is inferred by a successful import.
- If the runtime lacks OANDA practice API access, set the flag back to 0 and check the demo account's XAU_USD entitlement with OANDA support. OANDA account region/product access varies.
- **Never** place credentials inside CSV files, the browser, repository, PRs or test logs.

Review [official OANDA candle parameters](https://developer.oanda.com/rest-live-v20/instrument-ep/) and [Dukascopy historical export](https://www.dukascopy.com/api/data/get/historical-data-export) before enabling. The project's existing data-provider rights register remains controlling.
