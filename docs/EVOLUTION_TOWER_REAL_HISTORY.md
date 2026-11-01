# ATL Evolution Tower — historical XAU/USD BID/ASK research mode

## Scope

Evolution Tower can now switch an existing, saved synthetic cohort to a **frozen
research snapshot of actual historical provider XAU/USD M15 BID/ASK quotes**.
This is a separate research mode, not a qualification or execution engine.

- On the Evolution Tower page choose **OANDA practice BID/ASK** or **Dukascopy
  BID/ASK**, then press **Switch tower to real data**.
- The source adapter is called **on the backend**, requires existing owner login
  and CSRF authorization, and is disabled by default until the operator
  independently verifies the provider's private data-use/ML retention rights.
- For OANDA, set `ATL_OANDA_PRACTICE_RESEARCH=1` and the private
  `OANDA_V20_PRACTICE_TOKEN`. For Dukascopy, set
  `ATL_DUKASCOPY_RESEARCH_DOWNLOAD=1` and configure
  `DATA_STORAGE_DIR` for an appropriate private cache.
- Fail closed on absent source, malformed/hash-mismatched rows, crossed quotes,
  incomplete candles, insufficient history or generation mismatch. **No synthetic
  fallback** when a real-data activation is requested.
- The original 16 chromosomes and historical synthetic event archive are retained.
  Activation adds an auditable event at the next generation, resets visual rankings
  and starts a separate real-generation counter. The frozen source cannot be swapped
  repeatedly to cherry-pick results.

## Methodology and limitations

1. Accept 640–2016 strictly chronological completed M15 bid/ask observations
   from an existing server-side feed. The snapshot's canonical SHA-256 is
   checked before anything is persisted.
2. First 70% of observations are research **B** and used for repeated evolutionary
   fitness selection. The next 20% are **C**, displayed for monitoring only.
   Because C metrics are viewed repeatedly, C is **not** independent validation.
   The final 10% of fetched observations (D) is omitted from stored Evolution
   Tower state and cannot be evaluated by this engine.
3. For each completed bar i, derive price features and choose HOLD/BUY/SELL/CLOSE.
   Hypothetical execution uses the next bar's OPEN ASK to buy and OPEN BID to sell;
   positions are marked to next-bar midpoint CLOSE, with a side-specific exit.
4. Apply observed quote spread and separately labelled assumed slippage (3 bps
   per side), commissions (2 bps per side) and financing approximation (0.8 bps
   for any date change while holding). These assumptions **must not** be
   advertised as actual broker fills, margin, funding statements or achieved P&L.
   Exposure is capped at 0.5x and the simulation stops at 20% drawdown.
5. **Training-selection bias remains.** Using B again in successive generations
   produces in-sample model selection. This is exploratory research, NOT an
   independently evidenced edge. A longer licensed real history, independent
   walk-forward evaluation and an untouched final exam are needed before
   meaningful claims. Paper/live orders and promotion remain disabled.

## Verification

`python -m pytest backend/tests/test_evolution_tower_real.py
backend/tests/test_evolution_tower.py -q`

This runs deterministic fixtures and API security checks without real provider
credentials or network requests. To evaluate actual market data, the production
backend must separately have provider authorization, network access and the
environment settings above; the real source and hash are displayed in the UI.
Until those exist, the deployed tower remains in its previously saved synthetic
mode and accurately reports that limitation.
