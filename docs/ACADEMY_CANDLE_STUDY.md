# Imported XAUUSD Academy Candle Study (research only)

## What is implemented

After a CEO logs in, opens **Students → (student) → Academy**, the new
**Student Candle Study** panel lists imported, saved XAUUSD M15 datasets.
Select the dataset and tap **Start study** to run a read-only server-side
analysis and replay the resulting progression across batches on iPhone.

The server re-verifies the raw/canonical artifact SHA-256 values before
opening candles. The study respects a student's approved learning plan:
autonomous students can inspect `trend`, `range`, and `breakout` fixed
directional rules; directed students can inspect only rules in their plan.
A student directed solely to another market, or without a supported rule,
is explicitly blocked. There is no silent switch of markets/strategies.

## Correct point-in-time semantics

This is a **directional-observation lab**, not a learned trading strategy,
broker backtest, or neural trainer. Its rules are deliberately transparent:

- `trend`: predict continuation of the most recent close-to-close direction.
- `range`: predict reversal of the most recent close-to-close direction.
- `breakout`: predict continuation only after the current close breaks a
  preceding four-bar high/low envelope.
- A prediction is counted only after the following M15 bar has closed.
- Signals depend only on candles known at the decision time. Missing M15
  intervals, flat outcomes and abstentions are excluded rather than
  manufactured into successes.

Imported history is split into chronological **60/20/20** train,
development-validation and sealed holdout portions. Boundary embargoes
are applied before any signal is scored. The training study evaluates
consecutive, nonoverlapping batches of up to 96 M15 bars each. After
every **five completed training batches**, the *market student's rule
selector* can switch to the best-accuracy eligible rule over the previous
five batches; the selector is versioned even when the choice is unchanged.
Shared rules themselves **do not change** and no neural weights are trained.

The resulting selector is frozen for a separate descriptive evaluation
on the development-validation partition. The sealed final holdout is
never scored or exposed through this feature. The UI displays a rolling
price checkpoint chart and a second *directional accuracy* chart,
including batch/revision counts and the final development screen.

## Explicitly not included

- No trade entries, exits, fills, liquidation or realised net profitability.
- No M1 bid/ask price data inferred from M15 candles.
- No invention of a 70–80% trading win rate or claim of out-of-sample alpha.
- No closed-trade good/bad memory ingestion or neural weight changes.
- No auto-scheduler, persistent completed training checkpoints or student
  promotion; the study is computed on demand.
- No automatic Registrar, paper trading or live capital authorisation.

Stored owner archives remain quarantined until provider authenticity,
licensing/rights, session calendar, price convention and other quality
questions are independently verified. CI passing cannot establish
these facts.

## What remains for full trading-agent qualification

1. Obtain and record approved, legally usable market data provenance.
2. Independently validate M1 bid/ask and broker execution costs.
3. Link legitimate executed or sufficiently modelled trade outcomes into
   strictly separated train/development/holdout episode archives.
4. Train market-specific models/skill-selection policies; run independent
   walk-forward exams and positive net-after-cost risk tests.
5. Have the owner review the specific paper-trading pilot and explicitly
   approve it after all relevant integrity, Registrar and risk gates.
6. Keep any live-capital approval completely separate.

For the earlier dataset evidence gates and performance-review modules,
see `docs/post_sprint_11_qualification.md` and GitHub issue #18.
