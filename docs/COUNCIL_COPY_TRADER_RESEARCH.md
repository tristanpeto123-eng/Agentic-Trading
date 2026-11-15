# Council Copy-Trader Intelligence — Research-Only Design

**Status:** Proposed implementation contract; no wallet provider or live data adapter is connected by this document.
**Scope:** Reproduce the workflow shown in the supplied 11-second recording as a Council research capability.
**Execution:** Disabled. This module must not submit, mirror, or route real orders.

## 1. What the recording demonstrates

The recording presents this sequence:

1. Discover top-performing Polymarket wallets.
2. Analyse an individual wallet's trading history, win rate, position sizing, and markets traded.
3. Monitor portfolio value and recent trades.
4. Review each observed trade before copying it.
5. Apply visible checks for liquidity, 24-hour volume, one-hour price movement, and position size.
6. Approve or reject a candidate trade, with manual review also shown as an option.

The recording includes a creator-reported example return. It explicitly says the result is not independently verified. That figure is not a benchmark, expected return, or evidence of profitability.

## 2. Council workflow

```text
Provider adapter
   -> Wallet discovery
   -> Wallet history and portfolio snapshots
   -> Wallet quality / concentration analysis
   -> New-trade event detection
   -> Per-trade review (auto-review or manual)
   -> Research-only copy simulation
   -> Outcome reconciliation after resolution
   -> Market-specific student memory / training
   -> Independent Examiner
   -> CEO review of research evidence
```

The workflow is event-driven where the provider supports it. Polling frequency, rate limits, freshness limits, and outage behaviour must be defined by the selected provider adapter; none are assumed here.

## 3. Functional areas

### A. Wallet Discovery

Store provider wallet identifier, discovery source, first-seen time, observation window, and raw-source reference. Discovery rankings are leads only, not approvals.

### B. Wallet Analysis

Display, where provider data supports the calculation:

- realised P&L after identifiable fees;
- win rate with closed-trade denominator;
- total closed trades and observation period;
- average and median position size;
- market/category concentration;
- largest-position and largest-win/loss contribution;
- activity recency and turnover;
- equity curve and drawdown;
- unresolved positions and outcome coverage.

Every metric must show its time window, denominator, calculation basis, and data completeness. Unrealised and realised P&L must not be mixed.

### C. Trade Monitor

Capture each newly observed wallet action as an immutable event. Preserve provider event ID, wallet, market/contract, side, price, size, timestamp, source timestamp, ingestion timestamp, and raw payload hash. Deduplicate by provider event identity. Corrections and cancellations append new events; they do not rewrite history.

### D. Trade Review

Provide Auto Review and Manual Review modes. A proposed research-copy event receives a per-check result:

- market/contract identity and status;
- liquidity/depth sufficiency;
- recent traded volume;
- price movement / volatility;
- observed wallet position size;
- simulated follower exposure and concentration;
- price staleness and source integrity;
- market resolution / settlement rules where relevant.

Each check is **PASS**, **FAIL**, or **UNKNOWN**. UNKNOWN must fail closed. The system records a reason for every rejection. The recording's example checks are UI references, not validated thresholds. Numeric limits must be explicitly configured and versioned by the CEO before any research run.

### E. Research Copy Simulator

An approved candidate creates a simulated follower event only. Model realistic entry delay, price impact, spread/fees where applicable, partial fills, unavailable liquidity, and missed trades. Do not assume the follower receives the wallet's displayed price or fill.

The simulator records both the wallet's observed action and the follower's hypothetical result. It must not send orders to Polymarket, a broker, or any other venue.

### F. Council Learning

Separate wallet-behaviour observations from market outcomes:

- wallet behaviour: entry/exit timing, sizing, concentration, frequency, market selection;
- market context: information available at decision time;
- simulated follower outcome: net result after modelled costs;
- final outcome: resolution/settlement evidence and timestamp.

Only closed, reconciled, point-in-time-safe research episodes may enter the relevant market-specific training partition. No wallet's aggregate win rate or profit figure is itself a student label. Keep source, event, feature, and label hashes.

## 4. Critical ATL boundary

The current Agentic-Trading repository is a research-first XAUUSD academy. Its current S2–S11 evidence gates and XAUUSD market-data contracts must remain intact.

Polymarket event-contract behaviour is a different market domain from XAUUSD. Therefore:

- Do not feed Polymarket wallet actions or event outcomes into XAUUSD student memories or training.
- Do not treat event-contract prices as XAUUSD candles or as interchangeable market features.
- Build a distinct Polymarket research adapter, market identity, data contract, simulator, and market-specific student curriculum if this vertical is approved.
- Reuse generic governance, provenance, audit, queue, and Examiner patterns only where their contracts genuinely fit.
- Any future cross-market transfer is a separately tested research hypothesis, never an implicit shared-training path.

## 5. Governance and hard stops

- Research-only; no wallet copying or order execution.
- No provider access until an adapter, terms/rights review, rate limits, and source provenance are documented.
- Unknown/stale market data, unresolved wallet identity, incomplete trade history, or failed integrity checks block review.
- Auto Review can approve a candidate for **simulation only**; it cannot authorise execution.
- Manual review cannot override data-integrity failures or hard risk limits.
- CEO approval is required before changing thresholds, promoting a research curriculum, or enabling any future external integration.
- Existing Guardian, Sentinel, Examiner, and paper/live locks remain authoritative and cannot be bypassed by this module.

## 6. Proposed mobile UI

1. **Overview:** wallets tracked, new events, review queue, simulated follower P&L, data freshness.
2. **Top Wallets:** sortable wallet list with time-window selector and concentration / drawdown warnings.
3. **Wallet Profile:** equity curve, realised P&L, win rate, trade count, average position, market distribution, recent trades.
4. **Trade Monitor:** chronological wallet events with filters.
5. **Trade Review:** Auto/Manual selector, per-check PASS/FAIL/UNKNOWN, reason codes, simulated exposure, Approve for Simulation / Reject.
6. **Research Runs:** immutable run configuration, copied-vs-missed events, simulated fills, costs, outcomes, and checkpoint links.
7. **Council Report:** student-specific training provenance, independent examination, blockers, and CEO decision.

## 7. Acceptance criteria

- Wallet metrics reconcile to an independently reproducible event ledger.
- Closed-trade denominator, time range, unresolved positions, and missing data are visible.
- Duplicate events do not create duplicate simulated positions.
- Auto Review and Manual Review produce the same deterministic hard-gate outcomes.
- UNKNOWN, stale, or integrity-failed inputs cannot be approved.
- Simulation never assumes the source wallet's fill price is available to the follower.
- All costs and execution assumptions are explicit and versioned.
- Training data is market-specific, chronological, hash-bound, and separated from holdout evaluation.
- The Examiner evaluates the simulated follower strategy, not the source wallet's advertised performance.
- Automated tests prove no execution endpoint, credential, or order-submission path is introduced.

## 8. Blockers before implementation can connect to data

1. Select and verify the Polymarket data interface and permitted use.
2. Confirm which wallet history, fills, positions, market depth, volume, and resolution fields are available and historically complete.
3. Define the wallet ranking window and minimum evidence requirements.
4. Agree the CEO-configured per-trade risk limits and simulated follower sizing policy.
5. Design and test the market-specific event-contract simulator and its settlement accounting.

Until these are resolved, the UI may show schemas and fixture examples only; it must not claim live wallet discovery, live monitoring, training completion, or validated results.
