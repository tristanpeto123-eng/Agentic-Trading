# Historical Replay Engine — Sprint 3 (research only)

The `agentic_trading.simulator` module is **offline deterministic M1 bid/ask replay**, not a broker adapter or an authenticated web trading endpoint. It is independent of Scalp City. All existing user-imported M15 datasets remain in Sprint 2 quarantine and cannot run a qualified replay. Source verification/licensing and genuinely executable M1/tick observations are outstanding.

## Exact inputs

- A chronological sequence of *closed* UTC-aligned **M1** `QuoteBar` instances with separately observed **bid and ask OHLC**. Do **not** create ask candles by adding a fabricated constant spread to a real dataset; only the explicitly synthetic demo does so for unit tests.
- Bound `TradeProposal`, `TradeAssessment` and `GuardianDecision` with matching proposal UUID/revision/hash, and a quantity in **troy ounces**, not broker lots.
- Explicit fixed `ReplayCosts` specifying initial equity, two-sided commissions (USD/oz/side), fixed adverse slippage (USD/oz/side), max entry spread, exposure, risk fraction, leverage and maximum holding minutes.
- `EvidenceKind` and source SHA-256 metadata, plus a UTC `as_of` observation cutoff.

## Reproducible execution rules

1. Reject missing/denied Guardian approvals, mismatched proposal revisions, duplicate IDs, expired instructions, unsupported instruments, exceeded exposure/spread/risk/leverage and overlapping positions. Assessment time must be earlier than Guardian decision, and neither may predate the proposal.
2. Use the **first eligible M1 open** on/after the Guardian decision and before proposal expiry; a decision in the middle of a minute does **not** get that minute's opening quote.
3. Long buys at ask + adverse entry slippage, exits at bid - adverse exit slippage. Short sells at bid - slippage, exits at ask + slippage. **Spread is inherent in quotes and is never charged a second time.** Deduct commission once per side.
4. Long stops/targets use bid low/high; short use ask high/low. If both touch during one M1 candle, pessimistically assume stop first and set `ambiguity=true`. At a gap-through stop, use the worse of the stop and next opening quote; at a gap-through target, cap favourable fill at target.
5. With continuous M1 bars, an expired holding horizon closes on the completed bar's bid/ask close. Any missing minute *during an open position* or a position still open at the end of the tape is `UNRESOLVED`; neither receives invented exit P&L nor a Good/Bad label.
6. Immutable typed `TradeRecord` and entry/exit/rejection `LedgerEvent` records, equity/drawdown, and SHA-256 fingerprints of cost config, observed M1 quote sequence and the recorded journal make tests reproducible.

**Risk caveat:** This M1 OHLC model cannot resolve the intraminute sequence of stop/target hits or reproduce variable spreads within a minute, market depth, partial fills, queue priority, rejections, margin liquidations, swaps, conversion costs, or the broker's session calendar. Conservative stop precedence helps but does not remove uncertainty. No claims of accurate executable profitability without verified lower-resolution data and empirical execution assumptions.

## Try controlled fixtures

```bash
pip install -e './backend[dev]'
python scripts/demo_historical_replay.py
python -m pytest backend/tests/test_simulator.py -q
```

The demo uses **synthetic** bid/ask bars and visibly marks its financial figures as *not market performance*. It is not a benchmark or examination.

## Outstanding acceptance dependencies

- Independently verify an appropriately licensed, genuine >=12 month XAUUSD dataset and a compatible provider-specific M1 bid/ask quote tape with audited session coverage. The existing Dukascopy adapter is unqualified.
- Establish durable, signed/sourced input binding so `source_sha256` cannot merely be a caller-provided assertion. Ensure the source hash is checked against S2 registered artifacts.
- Connect data readout, automatic Guardian instructions and CEO trade detail UI only when S2 provenance and S4 Guardian contracts are linked end to end. Add empirical broker cost calibration/partial-fill modelling and session-gap policy before paper readiness.
- Independent Examiner (S7) owns evidence eligibility and qualification; **this module always emits `qualification_eligible=false`**, even if external metadata claims historical verification.

**No paper/live trading, broker connectivity or model learning is enabled.**
