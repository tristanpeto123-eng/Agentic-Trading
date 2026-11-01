# CFD Academy — isolated research foundation (opt-in)

Source: owner's *Self-Improving CFD Trading Bot System: Full Specification* (1 November 2026), sections 3, 6–9, and supplied `autolabel.py`. **This is a parallel experiment, not a replacement of the live Agentic Trading research stack.** No broker connection, student model promotion, order execution, live modes or external data fetch. The original app's existing safety locks are untouched.

## Contents

- `autolabel.py`: the user-supplied five-detector, gradient-boosted classifier with **only** the previously reviewed one-line fix to the final complete HORIZON boundary (`e + HORIZON > n`). All original definitions of RR=2, SL_ATR=1, HORIZON=24, minimum FVG=0.3 ATR, swing-confirmation=5, feature set, gross `y`, walk-forward and classifier settings are unchanged.
- `foundation.py`: strict UTC M15 midpoint OHLC + observed spread + recorded long/short financing charges, immutable SHA-256 source manifest, A/B/C/D chronological boundaries, purpose-limited A/B/C access, locked D, and a separate after-cost audit ledger for the **A skill slice only**.
- `test_foundation.py` and `test_labeller_regressions.py`: synthetic-only deterministic boundary, data integrity, cost, gap, separation, no-future-influence, detector prefix-invariance and tamper regression checks.
- `requirements-dev.txt`: optional research-only dependencies. Not imported by the hosted application.

## Installation and tests (local researcher or isolated runner)

```sh
python -m pip install -r research/cfd_arena/requirements-dev.txt
cd research/cfd_arena
python -m pytest -q test_foundation.py test_labeller_regressions.py
python autolabel.py --demo --skill fvg
```

## Contracts

Data columns exactly: `time,open,high,low,close,volume,spread,financing_long,financing_short`.

- Each `time` is an explicit timezone-aware **UTC M15 opening timestamp**; raw rows must already be strictly increasing and unique. The module **never** sorts or forward-fills; missing intervals remain missing.
- OHLC are explicitly designated **midpoint estimates**. `spread` is observed full bid/ask spread in price units **per M15 bar**. Zero or missing spreads reject the dataset. This does not establish real bid/ask stop or limit fills.
- `financing_long` and `financing_short` are **booked per-unit price costs attributed to each M15 bar**. Real CFD providers may charge on rollover and triple-swap days; source-derived charges must be supplied explicitly, using zero only where the verified schedule says none was booked. Don't interpret arbitrary per-bar interpolation as the broker's actual overnight financing.
- `CostContract` requires explicit adverse entry and exit slippage, round-trip commission per unit per side, plus a source reference. They are converted only to **price units per instrument unit**; position size, account currency, conversion, funding, margin, liquidation, and market impact are **not** inferred.
- `y` remains the **gross binary TP-first result** exactly as in `autolabel.py`; cost-adjusted `net_profitable`, `net_r`, gross, spread/slippage/commission/financing charges and any conservative stop-gap adjustments live in separate columns. No implicit relabelling of classifier targets.
- A stop touched in the same OHLC as the target still wins. A gap through a stop uses the worse bar opening midpoint for the overlay. Even then, midpoint M15 resolution cannot capture actual execution; all results are unverified research and `qualification_allowed=false`.
- A (oldest 50%): **skill training**; B (next 25%): **bot training**; C (next 15%): **selection**; D (newest 10%): **sealed final exam**. Access to D is **not implemented** in this foundation; no model training, selection or repeated ranking may look at D. Slice functions verify the manifest and deny role mixing, including tampering with the split boundaries.
- Label generation is only performed on a slice-only frame for A. A sample whose observed holding path crosses an actual missing M15 interval is dropped from the audit rather than pretending market time was continuous; labels end before A ends, so B/C/D candles cannot influence A labels.

## Python example (synthetic research only)

```python
from decimal import Decimal
from foundation import CostContract, create_manifest, prepare_skill_A

# data is a previously sourced, verified-as-formatted pandas DataFrame with
# the nine exact columns above. This does not verify its licence or fills.
manifest = create_manifest(data, instrument="EURUSD",
    provider_reference="YOUR_SOURCE_REFERENCE", rights_reference="YOUR_RIGHTS_REFERENCE")
costs = CostContract(slippage_entry=Decimal("0.00002"),
    slippage_exit=Decimal("0.00002"), commission_per_side=Decimal("0.00001"),
    source_reference="YOUR_BROKER_COST_SCHEDULE")
ledger, audit = prepare_skill_A(data, manifest, skill="breakout", costs=costs)
assert audit["qualification_allowed"] is False
```

The literal numbers above are illustrative API usage, **not real EURUSD costs**. Do not substitute them for a sourced broker spread/cost schedule.

## Outstanding gates — do not skip

1. Obtain appropriately licensed, source-verified CFD market data, an exact executable BID/ASK tape (preferably tick/M1), session calendars, and a verified cost + financing schedule. Six years is the stated target; this code does not pretend a small demo file meets it.
2. Implement quote-based barrier fills and quantity/account-currency P&L, liquidation, margin and financing before judging after-cost profitability. Midpoint M15 estimates in this first ledger are unsuitable for actual strategy qualification.
3. Freeze skill models trained only on A, then train bots only on B from frozen A-only outputs, select on C; implement a **one-time per-candidate D exam registry** with strict attempt accounting before D can ever be read.
4. Test a plain after-cost baseline, walk-forward stability, sample thresholds, random-walk leakage controls, data provider rights and repeated-champion selection bias.
5. Only after independent exams and owner approval should any demo/live interface be considered. Risk layer must remain non-learnable and outside the arena.

**Owner approval is still required** to change definitions in specification sections 7–9, or decide whether this parallel CFD arena ultimately replaces the existing Agentic Trading engine.
