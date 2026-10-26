# Historical research modes available in the mobile preview

The Trading > Historical screen has three **distinct research views**:

1. **Trade & equity demo** — click **Run historical demo**. Five fixed fictional proposals
   are processed by the existing conservative M1 bid/ask simulator, using manufactured
   quotes and fixed costs. The chart reveals trade entries, exits and realised net P&L
   only as simulated time advances. **These prices are synthetic and the orders were
   not produced by a trained agent.** Reported net profit or loss is a test-engine output,
   never evidence of actual trading performance.
2. **Play a CSV from this device** — select an XAUUSD M15 UTC CSV stored in Files.
   The browser validates the timestamp sequence and OHLC bounds, reveals candles
   chronologically and never uploads or persists the file. Maximum 12 MiB, 80,000 rows.
   Files must have exactly `timestamp_open,open,high,low,close[,volume]`, explicit
   UTC timestamps in ISO 8601, and only fully closed M15 bars.
3. **Saved candle replay / Data Engine** — server-side immutable imported data.
   Persistent PostgreSQL is required on Render Free, and imports remain quarantined
   until independently verified. Saved M15 data is **not** sufficient to reconstruct
   bid/ask M1 executions or valid net-P&L estimates.

The `GET /v1/historical/demo` API requires the CEO session. It returns only
fixed synthetic fixture outputs and changes no databases, students, training runs,
risk parameters, model permissions or trading modes. The ordinary
`historical_execution_enabled`, `paper_trading_enabled` and
`live_trading_enabled` capability flags remain **false**.

To progress from demo to a genuine historical agent simulation, obtain rights-cleared
timestamped M1 bid/ask quotes, bind frozen model inference and Guardian decisions
in chronological order, evaluate unseen intervals independently and verify all
costs, spread, slippage, stop/target ambiguity and drawdown gates. This UI release
does **not** complete that work.

The historical demo and local CSV are available even when Render's free
PostgreSQL connection has not been configured. An inactive free service may need
a cold start before the login page loads.
