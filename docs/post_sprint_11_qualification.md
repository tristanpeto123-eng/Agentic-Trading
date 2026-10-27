# Post-Sprint-11 historical qualification (research only)

Issue: #18. This implementation is **not a Registrar approval** and does not authorize paper/live execution.

## Input and provenance

Run the read-only audit on an owner-authorized CSV:

```bash
python scripts/audit_xauusd_archive.py /private/path/xauusd_m15.csv --output /private/path/xauusd_audit.json
```

Accepted schema: `time,open,high,low,close[,volume]` or `timestamp_open,open,high,low,close[,volume]`, UTC M15 open times, chronologically ordered. The importer rejects malformed OHLC, unfinished candles, duplicate or out-of-order timestamps. It records missing intervals and other warnings without padding or rewriting prices. Archive output is local/private; do not commit licensed raw candles, personal file paths, or proprietary datasets.

**Import is not source verification.** The provider, lawful data rights, quote basis, timezone, market sessions, dataset fingerprint, source URL and acquisition trail require independent evidence. Dataset filenames, broker names supplied in a CSV, user-entered boolean flags and passing CI are not proof of independent verification. Gaps around holidays/weekends require comparison with documented provider session calendars. A complete M15 OHLC archive **cannot** be converted into genuine M1 bid/ask tape or broker-quality fills.

## Metrics and evaluation

`agentic_trading.holdout_review.review_holdout` scores **already costed** `ReplayReport` objects. It must not invent bid/ask quotes. Provide predeclared UTC holdout boundaries, a frozen strategy version and a record of chronological train/validation/test and walk-forward folds.

The returned JSON includes net P&L, win rate, expectancy, profit factor (undefined when no losses), maximum drawdown, closed and unresolved trades, crossing-boundary trades and evidence hashes. It blocks a positive *performance screen* on incomplete exposure, insufficient trades, missing losses, or excessive drawdown. This screen is descriptive and does **not** certify genuine market performance, data rights, absence of overfitting, or independent holdout isolation.

All reports explicitly set independent holdout verification, Registrar approval, paper eligibility and live eligibility to false. No broker connection, student promotion or capital allocation is created by this work.

## Additional qualification evidence required

1. Genuine data with documented provenance and rights. Independent M1 bid/ask quotes for execution validation, or a separately disclosed and independently accepted model with explicit limitations.
2. Pre-registered strategy freeze and leak-free point-in-time signals. Chronological unseen folds with enough observations to judge robustness; model selection must not use final test data.
3. Cost-sensitive replay, tail losses, margin/liquidation, rejected/unresolved trade handling, realistic execution constraints, and no-trade baseline.
4. Reviewer/Registrar evidence and explicit decision. CEO explicitly approves a bounded, kill-switch-equipped **paper** pilot only after the prior gates pass.
5. Separate CEO approval, broker safeguards, risk limits, operational audit, and lawful permissions before any **live** trading.

**Status:** The repo contains tests and review utilities; it does **not** currently have source-certified independent real-data execution results or an authorized paper/live deployment.
