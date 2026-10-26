# Sprint 10 — CEO interface and Sentinel safety

Sentinel runs a bounded, on-demand integrity scan of known historical dataset artifact SHA-256, archived memory payloads, Academy job plans, expired leases, research Strategy DNA, peer lessons, neural checkpoint files and examination status. It records findings as `research_safe`, `attention` or `blocked`; **`research_safe` is NOT a source certification, clinical safety conclusion, paper/live trading permission or release approval**. The API uses CEO-authenticated read-only `GET /v1/sentinel/report`.

The `POST /v1/safety/emergency-stop` route is CEO-only, same-site + CSRF verified, logs an audit event and persists a locked latch. The latch has no unlock route. Paper/live capabilities are separately hard-disabled and remain so even if the `safety_latches` row is missing. Fail-closed by default.

Student Profile now provides Academy and Evolution read-only sections. Home contains Sentinel reporting, an actionable emergency-stop latch button, and source-verification alerts. Historical/Paper/Live continue to show no fabricated P&L or balances.

Before a public deployment, finish TLS, reverse-proxy rate limiting, database backups, auth security review, external service monitoring, resource quotas and audit retention. Sentinel cannot replace a broker risk engine or independently verify provider licensing.
