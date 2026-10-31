# XAUUSD M1 BID/ASK quote-side offline replay — research only

This provides a bounded, deterministic bridge between the structurally
audited, owner-supplied M1 BID/ASK CSV pair and *hypothetical* after-cost
outcomes. **It is not a model backtest, real order simulator, executable quote
feed, proof of profitable trading, or permission to place paper/live orders.**

It uses the existing local [structural audit](M1_BID_ASK_AUDIT.md), which
validates both raw CSVs and their matching close quotes, before replay.

## Private execution

Run on a local machine with the two export files. The raw files must never be
committed to this public repository.

    python scripts/replay_xauusd_m1_pair.py /private/xauusd_bid_m1.csv /private/xauusd_ask_m1.csv --output /private/m1_replay.json

Default research-only scenario: a **fixed, untrained** momentum sign from
five completed M1 midpoint closes; a $0.75/oz minimum observed move; one full
additional minute of simulated latency after the signal completes; 5-minute
holding period; 0.10 oz size; $0.05/oz commission *per side* and $0.20/oz
assumed slippage *per side*. These are chosen for illustrating accounting, **not
measured or calibrated from a broker**. Defaults can be changed for local
sensitivity checks, but doing so is *model selection*, not independent proof.

A signal becomes known only after the close of its input minute. Entries and
exits are on subsequent aligned candle opening quotes: long buys ASK and
sells BID; short sells BID and buys ASK. **The observed opening quote-side
difference already represents the spread. Do not charge spread a second
time.** Commission and slippage are modelled separately. A complete minute of
latency reduces (but does not eliminate) same-boundary timing optimism.

Quotes must be strictly positive, monotonic, aligned, synchronized and
internally valid; all used M1 bars, including lookback, latency, holding and
exit intervals, must be continuous. Missing minutes are not filled. The
demonstration never maintains overlapping positions or accesses future
candles to choose signal direction. It emits hash-linked outcomes with up
to 12 example marks and explicit research/rights/execution denial flags.

## Limits and next qualification steps

* A candle OPEN is **not** a synchronized executable bid/ask tick. Real order
  arrival, route latency, spread at execution, fills, venue constraints,
  variable slippage, margin, overnight charges and stop/limit path are unknown.
* Matching minute bars for a single day cannot certify 12 months of coverage
  or a stable statistical edge. The user-supplied 28 October 2026 pair is
  intentionally **not copied into the repository or the CI fixtures**.
* This fixed illustrative momentum rule is **not** the pinned trained
  student's signal generator and has no connection to trade execution.
* The report includes no independent source/licence attestation. Historical
  source permissions must be documented separately before qualification.
* A valid research system still requires a separate, sealed, independently
  verified walk-forward model evaluation and explicit CEO trading approval.

For regression tests: pytest backend/tests/test_xauusd_m1_quote_replay.py -q
