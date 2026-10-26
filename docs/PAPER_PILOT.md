# Sprint 11 — paper pilot readiness (activation BLOCKED)

The application is not a connected trading platform. The Sprint 11 scope implemented here is a conservative **readiness register**, not an active paper broker. `evaluate_readiness()` reads actual records and fails closed. Client claims that a provider is verified or a backtest is profitable cannot unlock the service. A forged `HistoricalDataset.state='verified'` is still insufficient.

CEO paper-review requests are scope-bound by student/model hash/market, virtual capital ceiling and ≤2% nominal per-trade risk. Such a record has status `blocked_review_only`, `authorises_trading: false`, is idempotent, content-hashed, and audited. No API route to create a review request or activate a paper account is enabled in this sprint; the service helper is available for controlled future review only. This protects the locked owner-approval policy.

The Trading → Paper screen exposes the truthful missing prerequisites: legitimate/appropriate licensed 12 months of XAUUSD (ideally M1/ticks bid/ask), provenance rights and timestamp checks, sealed walk-forward holdouts, independent exam qualification, a verified Registrar, paper execution and reconciliation implementation, CEO approval of a specific version/market/capital/risk scope, secure hosting and emergency stops. Until those exist, paper and live operations remain disabled. No synthetic fixture profit is accepted as genuine trading performance.

Next phase requires explicit CEO review of an exact deployment candidate and proof of the above. **Never confuse research infrastructure completion with readiness for trading**.
