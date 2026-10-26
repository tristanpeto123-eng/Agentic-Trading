# Free Render iPhone preview — research only

This preview uses one Render **Free Web Service** built from the root Dockerfile,
served over HTTPS as a same-origin React + FastAPI application.

**Do not treat this as a production environment.** The web server may sleep after
inactivity. Its filesystem is ephemeral: a local SQLite account, students and
imported files can disappear on restart. The preview therefore sets
`PREVIEW_DISABLE_IMPORTS=1` until durable file storage is available.

## Resources

- Render web service: `agentic-trading-iphone-preview-2026`, Free, Frankfurt.
- Separate Render Free PostgreSQL instance:
  `agentic-trading-iphone-preview-db`, Frankfurt.
  The free database expires on **2026-11-25** and must be upgraded or replaced
  if the user wants retained data beyond that date. The created database's
  connection string is not available to this integration and must be copied
  **inside Render Dashboard**, never into GitHub or a chat.
- Until the database URI is connected the web service uses **temporary SQLite**
  and must only be used for disposable layout evaluation.
- No market-data imports should be made on Render Free without separate
  persistent object storage and restored integrity/retention checks.

## Link PostgreSQL from iPhone Safari

1. Open Render Dashboard > PostgreSQL > `agentic-trading-iphone-preview-db`.
   Copy its **Internal Database URL** using Render's secure UI. Keep it private.
2. Open Render Dashboard > Web Services > `agentic-trading-iphone-preview-2026`
   > Environment > `DATABASE_URL`. Replace the temporary SQLite value with
   the internal database URL you copied. Save changes and let the service redeploy.
   Backend settings and migrations convert `postgresql://` to
   `postgresql+psycopg://` to use the installed psycopg v3.
3. Check the Render deploy logs for migrations reaching revision `0009_s11`,
   and `/health` responds `{"status":"ok"}`.
4. Only **after** linking PostgreSQL, open `https://<render-web-host>/setup`
   in Safari. Use your own CEO email, a strong unique 12+ character password
   and the value of `PREVIEW_SETUP_TOKEN` from the web service's
   Environment tab. Keep the setup code secret.
5. After creating the CEO, remove `PREVIEW_SETUP_TOKEN` from Render.
   The setup route refuses to create another CEO.
6. Sign in at the Render web URL. Add it to iPhone Home Screen from Safari if
   desired. Inspect Students, Skills, Academy, Examiner and CEO dashboard.

## Safety notes

- Public HTTPS login page, **authenticated CEO API**. The app has basic
  in-process login throttling only, not a production distributed WAF/rate limit.
- Free PostgreSQL has a time limit; export anything valuable before expiry.
- No model qualification, broker integration, real or paper order execution.
- No running neural training workers. Trading and automatic learning remain
  disabled and unqualified.
- Keep provider data, access tokens, account credentials and personal market
  data out of the public repository.
- Railway deployments and stored data were not altered by this Render preview.
