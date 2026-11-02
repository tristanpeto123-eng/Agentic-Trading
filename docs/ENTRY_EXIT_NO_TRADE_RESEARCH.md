# ATL Entry/Exit Quality Research — no-trade benchmark

**Status:** offline research infrastructure only. Not an agent policy, independent performance attestation, or trading qualification.

This experiment addresses the finding from PR #62: maximizing toy fitness can select a policy that never trades. It distinguishes **zero-trade abstention** from **after-cost trading competence** rather than awarding rank for activity or considering zero return a profitable strategy.

## Research contract

1. A paired XAUUSD BID/ASK M1 CSV (UTC `timestamp,open,high,low,close`) is verified structurally with the preexisting strict `qualify_pair`. Missing minutes, crossed spreads, mismatched sides and missing provenance *fields* fail closed. **Field presence is not independent source or licence attestation.**
2. The full dataset is divided into chronological indices: initial **60% TRAIN**, fixed embargo of `lookback+holding+latency+1`, **development window up to 80%**, with **final 20% excluded from scoring**. The entire source is hashed and structurally checked, but sealed observations are not used in feature construction, strategy comparison or reporting.
3. Eight *fixed, precommitted* rules are compared **on TRAIN only**: momentum/reversal of completed five-minute midpoint change with thresholds 0.25, 0.50, 0.75 or 1.5 USD/oz. No ML fitting, no use of future candles to choose directions, no trade-count reward.
4. Each signal is acted on only at a **later quote-side candle OPEN**, after one full minute of simulated latency. Long enters ASK, exits BID; short enters BID, exits ASK. The observed spread is already included. Fixed additional per-side slippage and commission are deducted. No concurrent positions.
5. To remain a research candidate, a strategy needs **at least three TRAIN trades and net return strictly greater than the no-trade (zero) baseline**. If none pass, the correct selected action is NO_TRADE, explicitly marked as an abstention rather than a winning strategy.
6. The single selected TRAIN rule is observed on the non-sealed development partition **after selection is frozen**. The development score cannot alter the selection. No use of the sealed terminal slice.
7. The resulting report contains train candidates, cash baseline, selected development behaviour, total gross/friction/net results, drawdown and a small set of timestamped hypothetical entries. It always denies source attestation, trading qualification, automatic promotion, paper and live execution.

### Run locally (only when source-use permissions allow)

```bash
python -m unittest discover -s tests -p 'test_entry_exit_quality.py' -v
python scripts/evaluate_entry_exit_quality.py /private/xau_bid_m1.csv /private/xau_ask_m1.csv \
  --provenance-json /private/source.json --output /private/entry_exit_report.json
```

The local `source.json` must contain `provider`, `instrument`, `source_url`, `retrieved_utc`, `license_reference` and `permitted_use`. The report *never* claims these assertions were independently verified. Do not publish provider quote files.

### What is not established

- Candle OPEN is not a synchronized executable tick. Real broker fills, latency, spread at arrival, slippage, leverage/margin, funding and venue failures remain unmodelled.
- A fixed-lookback rule on synthetic fixtures does not prove profitability on XAUUSD, and a single development partition is not a walk-forward out-of-sample examination.
- The no-trade benchmark is necessary but insufficient; market regimes, execution realism, minimum eligible trade counts and sealed forward periods must be evaluated independently.
- Comparing several strategies on TRAIN introduces optimisation bias; the uninspected terminal slice and external Examiner remain necessary.
- This module does **not** connect to the open five-batch policy-trainer PRs, existing saved students, Evolution Tower chromosomes or the Guardian. Nothing is promoted.

**Next Council gate:** obtain independent provider-rights evidence and sufficient genuine timestamp-aligned historical BID/ASK coverage, replay frozen student signals chronologically under realistic costs, independently verify sealed walk-forward results, and keep Owner approval before any paper-trading activation.
