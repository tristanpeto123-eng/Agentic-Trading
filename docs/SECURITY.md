# Security & Safety Baseline

1. The GitHub repository is **public by CEO choice**. Public source visibility does not imply public API deployment.
2. Sprint 0's unauthenticated API is strictly **localhost development only**.
3. Never commit secrets, API keys, brokerage keys, passwords, bearer tokens, individual trading datasets or private account records.
4. `.env` and local databases are ignored; `.env.example` holds placeholders only.
5. CEO role fields in a request are **not authentication**; future sensitive endpoints must verify identity server-side with persisted approvals and audit logs.
6. No live or paper execution adapters or broker configuration are enabled in Sprint 0.
7. Synthetic and counterfactual data cannot qualify a research champion.
8. Guardian gate denies missing, stale, mismatched or unapproved proposals.
9. No model may modify its own live deployment or risk limits.
10. Before paper deployment: session security, RBAC, CSRF safeguards, migrations, secrets management, backups, and position reconciliation.
