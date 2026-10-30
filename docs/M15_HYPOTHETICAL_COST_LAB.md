# XAUUSD M15 hypothetical good/bad outcome lab (research-only)

The directional selector built in PR #19 achieved a low-50% descriptive
classification score on the owner's uploaded XAUUSD M15 archive. Classification
is **not** a trade win rate or proof of after-cost profitability.

This PR adds an **explicitly assumed-cost scenario** alongside the existing
Candle Study on **Students → Student → Academy**. It does not train a neural
network or alter execution permissions.

## Scenario and accounting

- Each rule (fixed trend/range/breakout heuristic) receives only completed
  information through the close of candle `i`.
- An illustrative entry is assigned to candle `i+1`'s **observed M15 open**
  and an illustrative exit to that same candle's **observed M15 close**.
- Missing intermediate M15 slots are excluded. No trade is fabricated
  across a known data gap. No same-bar hindsight target/stop is simulated.
- Directional gross USD for each hypothetical exposure is
  `direction * (next_close - next_open) * quantity_oz`.
- From gross USD, deduct a **declared assumed** full round-trip spread plus
  twice each assumed per-side slippage and commission. These are *not*
  independently observed bid/ask costs.
- Initial scenario equity: **$1,000**. Hypothetical size: **0.10 oz**.
  The default illustrative assumptions are **$0.50/oz full spread,
  $0.20/oz slippage per side, $0.05/oz commission per side**.
  The assumed round-trip friction is thus **$1.00/oz** or
  **$0.10 per example** at the assumed size.
- A hypothetical **good** outcome has net USD > 0, **bad** has net USD < 0;
  zeros are **flat**. Record magnitudes, gross P&L, assumed costs,
  net result, expectancy, maximum drawdown, and scenario profit factor.

Fixed tactics remain unchanged. Only the **student's exploratory selector**
may be revised **after** every five completed training batches using the
highest net-after-assumed-cost score of those training-only batches.
The final selected rule is frozen for a distinct development-validation
score. Final holdout is sealed and never read for predictions, selection
or scoring. Selector revision numbers are not neural weights, mastered
skills, durable student memory or production-trained models.

## Scope and limitations

This is **not a historical M1 bid/ask simulator** and must not be presented
as one. It uses M15 OHLC as a *reference price*, whose bid/ask/transaction
price convention remains unverified. It assumes zero entry delay beyond
stated slippage. It models **no stop priority, intrabar trading path,
margin, leverage, liquidation, funding, borrow, session-specific spread,
partial fills, portfolio aggregation, risk sizing or execution latency**.
Those omissions can materially change a profitable-looking scenario.

The server endpoint
`GET /v1/students/{id}/m15-trade-scenario?dataset_id=...`
is read-only, CEO-authenticated and strictly scoped to a hash-checked,
quarantined XAUUSD M15 dataset and the student's research-plan tactics.
The response is deterministic and reports provenance uncertainty,
assumptions, a fingerprint, batch equity, train/development scores and
a small, **ephemeral** sample of good/bad outcomes.

**No** `TradeExperience`, `TrainingRun`, `ExamRun`, approved
checkpoints, paper orders or live orders are written. It is **not eligible**
as independent profitability evidence. No promoted/approved student state
is changed by running this study.

## What actually gets Kairo ready for training

1. Independently verify archive provenance, price convention and rights.
2. Obtain authentic, licensed M1 bid/ask quotes. Use the pre-existing
   `simulator.replay` with point-in-time generated setups and its
   rejection/gap/stop/target rules.
3. Generate verified source-bound, completed after-cost episodes **only**
   after the trusted research importer has been designed and approved.
4. Train neural/policy models on strictly partitioned TRAIN episodes, frozen
   shared skill definitions and independent sealed Examiner data.
5. Require walk-forward net profitability after costs, risk constraints,
   Registrar review and explicit separate CEO paper/live approvals.

Never retrofit assumed M15 fills as if they came from the M1 bid/ask tape.
