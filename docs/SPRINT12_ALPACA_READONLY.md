# Sprint 12 (phase A): read-only Alpaca Paper Account dashboard

**Implementation status:** Draft pull request for review, not an authorised trading rollout.

## Scope

- Authenticated CEO-only `GET /v1/paper/account`, `Cache-Control: no-store`.
- Calls Alpaca **paper** Trading API only: `GET /v2/account`,
  `GET /v2/positions` and `GET /v2/orders?status=open&limit=500`.
- UI: Trading → Paper → Simulated account overview. Displays account status,
  masked account ID, virtual cash/equity/buying power, open position/order counts,
  limited current-position detail and snapshot timestamp.
- Manual Refresh; no automatic polling, market orders, order placements,
  cancellations, fills, trading models, data source validation or capital allocation.
- Read-only account monitoring **is not a broker execution connection**.
  `broker_connected` remains false in capabilities and existing readiness gates
  stay in force; paper/live trading remain explicitly disabled.

## Credential configuration

The earlier successful GitHub Actions workflow establishes that a matching key
and secret can authenticate from a workflow. **Actions repository secrets do not
automatically flow into the running FastAPI service.** For a secured backend
runtime, configure these secrets through its private environment/secret manager:

- `APCA_API_KEY_ID`: Alpaca **paper** Trading API key ID
- `APCA_API_SECRET_KEY`: matching secret
- `ALPACA_PAPER_EXPECTED_ACCOUNT_ID`: optional but recommended, exact account
  ID copied privately from Alpaca; mismatches cause fail-closed 503 before
  positions/orders are read.

For compatibility, if **neither** `APCA_*` environment variable is set,
the endpoint also accepts the complete legacy pair
`ALPACA_PAPER_API_KEY_ID` and `ALPACA_PAPER_API_SECRET_KEY`.
It never mixes one variable from each naming convention. The existing dedicated
BTC student diagnostic still uses its own legacy variable names and mandatory
expected account ID.

Never put actual credentials in a GitHub commit, `.env.example`, frontend code,
browser storage, GitHub issue, PR comment or public screenshot.
The `.env` file should remain untracked; only configure actual values in
private backend settings or a locally untracked `.env` with appropriate care.

If runtime keys are missing, the endpoint responds with `configured:false`,
so the UI displays an actionable setup notice without attempting Alpaca requests.
Unauthorized users receive HTTP 401. API failures and identity mismatches
are intentionally shown only as a sanitized 503, not raw broker bodies or keys.

## Read-only response contract

When configured and reachable:

- `paper_api_readable:true`: the key pair authenticated for a **snapshot**.
- `account_bound:true`: optional expected account ID matched; false means
  read-only observation without explicit backend account pinning.
- `account_suffix`: only last four account ID characters, never the full ID.
- `cash`, `equity`, `buying_power`: string amounts in account currency,
  **not** profitability of the Agentic Trading research students.
- `positions`: up to 30 normalized holdings; count reflects the returned
  holdings list. Excludes broker order IDs, account number and raw payloads.
- `open_orders_count`: capped at 500 records; `open_orders_count_capped`
  explicitly signals when more might exist.
- `paper_trading_enabled:false`, `live_trading_enabled:false`,
  `broker_order_execution_enabled:false`,
  `student_order_execution_enabled:false`.

The S11 paper readiness report is still the governing activation lock.
No qualification, account approval or order route was created by S12 phase A.

## Review / verification

Run locally, after installing the existing requirements:

```bash
python -m pytest backend/tests/test_alpaca_account_readonly.py -q
python -m pytest backend/tests -q
cd frontend && npm ci && npm run build
```

Required acceptance checks: CEO authentication, no-store response,
missing-runtime-secret handling, mismatched-account rejection before any
secondary read, no-order HTTP methods, no secret/ID/order payload leakage,
responsive frontend build, and unchanged absence of order endpoints.
Workflow CI must pass on the **actual head** before owner merges.

## Later phases (not implemented or authorised here)

Only after separate evidence/approval: hardened deploy architecture, verified
data rights, independent Examiner and Registrar, risk engine, order reconciliation,
paper execution design and staged dry-run qualification. Never infer paper-order
authority from successful read-only authentication.
