# Render deployment revision parity and auto-deploy incident

**Observed 3 November 2026.** Render service `agentic-trading-iphone-preview-2026` targets
`tristanpeto123-eng/Agentic-Trading`, branch `main`, with `autoDeploy=yes`,
`autoDeployTrigger=commit`. Despite these settings, Render recorded only
API-triggered builds, including the 2 November release. New commits were not
automatically deployed.

On 3 November at 10:33 UTC, a recovery deploy of `9fb51fbc733535b32a16be0d471f0d287023b70f`
completed successfully. This establishes point-in-time revision parity,
**not that the Git integration is repaired**.

## Detection

- Render sets `RENDER_GIT_COMMIT` automatically at runtime on Git-based services.
- The unauthenticated `GET /health` response reports its 40-character commit
  SHA as `deployed_commit`. On local environments or when unset, this is
  `null` rather than an invented revision. Health and authentication behaviour
  otherwise remain unchanged.
- GitHub Actions workflow **Render live commit parity watch** runs at 00:17,
  06:17, 12:17 and 18:17 UTC, as well as on explicit manual dispatch. It compares
  the public health revision against the triggering `main` commit and retries
  temporarily while Render spins up. A mismatch **fails**, never triggers
  deploys or assumes the site is current because it returned HTTP 200.
- This is a status/alert mechanism, **not a fix for deployment**. It has no
  Render API key, deploy-hook URL or broker credential.

## Root cause to inspect in the account dashboard

1. In the Render service, open **Settings → Build & Deploy** and confirm
   repository, connected Git credential, linked `main` branch and Auto-Deploy
   mode. Mode **On Commit** is appropriate when immediate Git events should
   deploy. This service already reports the equivalent API setting, so simply
   reading `autoDeploy=yes` does not prove the trigger works.
2. Check the **Render GitHub App** installation and ensure
   `tristanpeto123-eng/Agentic-Trading` is included under Repository access.
   Official guide: https://render.com/docs/git-provider .
3. If the service creator's Git credentials lost repository permission, update
   that service's **Git Credentials** from Settings. Verify permission before
   saving; reconnecting is an account-owner action.
4. Merge a reviewed research-only change, then confirm the Render **Deploys**
   page records a Git-triggered deployment matching the new SHA. Monitor the
   parity-watch workflow; a manual API deploy is recovery, not resolution.

Render deployment docs: https://render.com/docs/deploys .
Default `RENDER_GIT_COMMIT` environment: https://render.com/docs/environment-variables .

## Safety invariants

All existing CEO authentication, Guardian, hidden broker/order write routes,
research-only model gate and paper/live disablement remain unchanged. A green
parity watch indicates deployed source revision only; **not** a strategy,
dataset provenance, user-rights, live fill model or independent qualification.
