# Alpaca BTC/USD: private historical source capture (research only)

## Observed connected account capability — 31 October 2026

The connected Alpaca paper account reported ACTIVE with USD 200 of simulated
cash. BTC/USD resolved as a supported crypto instrument, while XAUUSD was not
found. Through the connected API, the Director fetched and structurally
inspected:

- 335 daily BTC/USD candles, 1 Nov 2025 through 1 Oct 2026.
- 169 hourly BTC/USD candles, 1–8 Sep 2026.
- 8 historical Level 1 BTC/USD BID/ASK observations, 29 Oct 2026.

No duplicates or malformed OHLC quotes were observed in these limited samples.
This does not prove continuous one-year history, broker fills, data usage
permissions, independent source attestation, or any performance outcome.

Official documentation:

- https://docs.alpaca.markets/us/docs/historical-crypto-data-1
- https://docs.alpaca.markets/us/docs/historical-api
- https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf

Alpaca specifically says crypto bars can be constructed from quote midpoints,
including when no trade takes place. Consequently BAR prices are NOT guaranteed
executable prices; an OHLC midpoint cannot simply be substituted for the
BID or ASK at execution. Level 1 snapshots are not broker order-fill evidence.

## Fail-closed implementation

The historical BTC adapter only performs fixed-host GET requests to Alpaca's
v1beta3/crypto/us/bars and v1beta3/crypto/us/quotes endpoints. No account
keys, account mutations, broker orders or public endpoints were added.
The adapter:

- Requires an explicit opt-in for network fetching AND an acknowledgement
  limiting use to personal, non-commercial private research.
- Allows BTC/USD only, bounded 31-day hourly/daily OHLC windows or
  30-minute Level 1 quote windows, and 1,000 records per page.
- Checks UTC times, completed bars, positive OHLC prices and valid bounds,
  non-negative volume, quote bid <= ask, correct symbols and page limits.
- Rejects duplicates/out-of-order bars, truncated/unexpected payloads,
  request errors, repeated pagination and responses beyond safe limits.
- Produces immutable local JSON Lines with SHA-256 digests and a restricted
  manifest with rights_verified=false, qualified=false and trading=false.
- Never commits raw quotes, embeds keys in source, promotes a strategy or
  unlocks paper/live trading.

Local private-runner example AFTER confirming applicable account terms:

    python scripts/fetch_alpaca_btc_history.py \
      --from-utc 2026-09-01T00:00:00Z \
      --until-utc 2026-09-08T00:00:00Z \
      --kind bars --timeframe 1Hour \
      --out-dir /private/alpaca-btc \
      --fetch --private-research-only

For quotes, use --kind quotes with <=30 minutes and a separate private
capture. The script refuses an output destination inside the public repo.
Repeat bounded windows for broader history, verifying calendars, gaps and
licence rights before treating any aggregate as research evidence.

No network download runs in CI. All regression inputs are synthetic and
in-memory; they demonstrate parser correctness, not live provider continuity.

## Source rights and qualification

Acquiring API records does not make Alpaca market data free for commercial
resale, sharing with SaaS customers, publishing in public GitHub or
unrestricted cloud processing. Do not claim those rights. Retention,
private ML training, derived outputs, cloud workloads and any commercial use
require the applicable provider terms and, if needed, written permission.

Keep BTC and XAU model and datasets strictly separated. There is still
no independently licensed and validated year-long XAUUSD BID/ASK tape.
All source/right, holdout, Examiner, Registrar and CEO activation gates remain
blocked until independently satisfied.

## XAU/USD supplier status

OANDA documents historical M1 BID/ASK through its v20 candle endpoint
(price=BA, granularity=M1), but requires an eligible account and access token.
No account has been created, and cloud research/AI rights require confirmation.

FXCM publishes premiumdata@fxcm.com for longer/bespoke historical BID/ASK.
Its public example price downloads do not constitute permission to copy
gold price data into a future commercial SaaS.

Dukascopy's decoding script is NOT permission for automated collection.
Keep provider fetches disabled pending applicable written consent.
