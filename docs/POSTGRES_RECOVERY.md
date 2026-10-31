# Production data recovery: rehearsed structure versus actual backup

The GitHub workflow `postgres-recovery.yml` spins up an **ephemeral**
PostgreSQL 16 database, runs Alembic through head, seeds one clearly
artificial CEO row, takes a restricted-permissions `pg_dump -Fc`, restores
into a different database, verifies the data and current migrations, checks
the policy-candidate schema and confirms broker order routes are absent.
Nothing from the actual user, hosted database or trading account enters CI.
The transient dump is deleted. This is a **local recovery rehearsal only**,
not proof that real production backups exist.

## Actual Render PostgreSQL follow-up

The current Render Free Postgres instance
`agentic-trading-iphone-preview-db` is reported to **expire on 25 November
2026**. Before then, the owner-controlled service requires an actual database
retention/migration decision, private encrypted snapshot, restore to an
independently protected target, new application binding, followed by health,
migration, integrity, authentication and safety-latch checks.

The hosted Render MCP cannot externally query the database because its empty
IP allowlist denies external access. Do not broaden to `0.0.0.0/0` for a
convenience check. Database contents, secret material and dumps should never
be placed in a public repository, job logs, public PR or unencrypted device
download. Restore must be verified with credentials managed privately by the
host and owner.

This workflow is explicitly research-only and changes no host plan, billing,
credentials, live database, provider rights, student promotion or broker
execution permissions. It does **not** alone satisfy release gate #20.
