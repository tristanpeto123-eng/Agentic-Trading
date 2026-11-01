# ATL Evolution Tower — v1 experimental research visualisation

**Status:** synthetic-only, unqualified, research-only. A mobile-first Three.js
view is wired to a real persistent Python evolutionary simulation. The graphics
are not proofs of alpha; agents never place paper or live orders.

## Operation

From the CEO console, open **Trading → Evolution Tower**, create the initial
16-agent cohort, and press **Run next generation**. Or enable the clearly labelled
**Auto-evolve in this tab** switch while the browser remains open. The interface
always reads/writes authoritative PostgreSQL snapshots. On reload, the latest
generation and archive reappear. Nothing continues while the browser is closed.
No server background worker, job scheduler or 24/7 service has been deployed.

The building has 100 floors and an orbit/pinch-zoom exterior camera, not a
first-person character camera. Click a robot or ranking to inspect its saved
genome hash and generation. The building elevator and elimination animation
are visualisations of saved events, not trading actions.

## Engine

- An initial deterministic 16-genome population, each with a real 6→8→4 neural
  policy (92 scalars). Actions: hold, buy, sell, close.
- Each generation runs the same frozen chromosomes on two **separately seeded
  toy random-walk** tapes called synthetic B (384 observations) and C (192).
  Each agent's signals use only currently completed information; execution is
  calculated on the next observation. No A-labelled skill training exists in
  this preview. D is never generated or inspected.
- The pathwise simulator includes a bid/ask **assumption** (12 bps spread),
  adverse slippage assumption (3 bps/side), commissions (2 bps/side) and a
  synthetic overnight charge (0.8 bps per 96 bars). These are not actual CFD
  quotes or broker fills. Margin exposure is limited to 0.5x equity by immutable
  application logic. The hard drawdown kill threshold is 20%.
- A bounded fitness objective combines toy net return, maximum drawdown, a
  Sortino-style downside proxy and a trade-count penalty. The best half by
  selection-tape fitness can survive; failed/risk-breached competitors are
  archived. Children inherit real parent chromosomes with Gaussian perturbation,
  receive new immutable content hashes and start at the nursery.
- Floors represent a relative *toy simulation* rank. No bot is placed above
  Floor 49 and the Penthouse remains locked; no simulated strategy is promoted
  to a qualified champion, demo broker or live broker. A flat baseline earns
  zero and is kept as the benchmark.
- B and C are **toy synthetic slices only**, not the signed-off 50/25/15/10
  real CFD A/B/C/D training protocol. Repeated evolution over toy C does not
  qualify any model. When real data is introduced, training/selection
  separation and untouched D examination must be independently enforced.

## Storage and API

Migration 0013 adds an owner-scoped generation state table plus an append-only
generation event table. State, archive events and neural chromosomes have
canonical SHA-256 hashes verified on every protected API read/update. The API
supports authenticated CEO reads and CSRF-guarded, single-generation writes:

- GET /v1/evolution-tower
- POST /v1/evolution-tower/start
- POST /v1/evolution-tower/advance {"expected_generation": 0}

The generation number is checked under a database row lock, preventing
overlapping generations from the same stored state. Browser responses exclude
full model weights. The archive stores actual culled-agent ID, reason, selected
evaluation metrics and the previous floor. History is append-only.

## What is intentionally not implemented

This is **not** the revised CFD trading system's six-years-of-bid/ask data
training arena. Missing gates include verified/licensed broker source, production
execution-cost ledger validated on actual broker quotes, A-slice skill training,
B-slice policy learning using frozen validated skills, C-slice model selection
with multiple-comparison corrections, sealed D, independent final examination,
paper-demo broker binding, live trading and the 24/7 job runner.

The only plausible next release is a separate worker process with lease/recovery
and point-in-time verified input data. Its outputs must be distinguished from
this toy sandbox and may never silently upgrade these simulated fitness numbers
into trading permissions.

**Security:** No keys, accounts, broker clients, order endpoints or trading
authorisation are referenced by the new module.
