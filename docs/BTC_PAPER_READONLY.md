# BTC Alpaca paper adapter — read-only prototype (not activated)

This change adds a **CEO-authenticated, BTC-student-scoped GET diagnostic**:
`GET /v1/students/{student_id}/paper/btc/diagnostics`.

The student must be on a **directed learning plan with BTCUSD**. Before
credentials are supplied, the endpoint returns a truthful unconfigured status.
When configured, the backend only reads the selected paper account, open
positions, open orders and the BTC/USD bid/ask. No new account is created, no
trading strategy is deployed, and neither paper nor live orders are possible.
The main `paper_trading_enabled` and `broker_connected` execution capability
flags remain false.

## Secure setup (owner action required)

On the **dedicated SC-PAPER-BTC account** in Alpaca, generate **paper API keys**
(not live keys). Do not copy the keys into ChatGPT or into GitHub.

In your protected Render web-service Environment page, set:

- `ALPACA_PAPER_API_KEY_ID` — dedicated BTC paper account key ID.
- `ALPACA_PAPER_API_SECRET_KEY` — matching paper secret.
- `ALPACA_PAPER_EXPECTED_ACCOUNT_ID` — the corresponding Alpaca account ID,
  confirmed separately inside the paper account.

These are **different** from the temporary Alpaca→ChatGPT OAuth authorization
in the screenshot. That ChatGPT connection cannot supply credentials to Render.
The API is hard-coded to **https://paper-api.alpaca.markets**, and only uses
GET calls to the paper account and crypto market-data services. The expected
account ID prevents confusing the BTC account with the SOL/ETH paper accounts.

Avoid setting these on the current public free preview until its hardening and
retention review is complete. Use a dedicated secure deployment with access
controls, secret management, egress restriction and alerts. Keys must never
appear in frontend variables, logs, chat messages or source control.

## Verification and next gates

1. Create or choose a directed BTCUSD student. Open the diagnostic endpoint
   after CEO login, using the student's exact ID.
2. Verify account ID suffix, $200 *budget* (not claimed as actual broker
   balance), BTC bid/ask, and zero open orders/positions. If either count is
   nonzero, isolate or reset the dedicated paper account.
3. Prove historical BTC replay integrity, strategy version fingerprints,
   realistic bid/ask spread, fees/slippage and walk-forward holdouts.
4. Build a separate, idempotent paper order engine with reconciliation and a
   tested emergency-stop path; require a separate CEO approval for exact
   student/version/account/capital/risk scope.
5. Only then evaluate activation. Current readiness is **BLOCKED**.

No strategy has been qualified from this diagnostic, no profit rate has been
established, and no trade has been submitted. BTC spot does **not** support
short selling via this Alpaca paper account. Do not infer continuous execution
from a ChatGPT conversation or the temporary OAuth permission.
