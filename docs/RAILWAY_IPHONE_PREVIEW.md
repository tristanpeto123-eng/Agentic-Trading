# Railway iPhone evaluation preview

This is a **research-only evaluation build**, not a qualified trading or production-grade deployment. It is one Railway web service (Python FastAPI plus built React) with a persistent volume. The service has **no broker, paper or live order routes**.

## Setup (done from iPhone Safari)

1. Create a private Railway project named `Agentic Trading — Preview`.
2. Provision a service from the GitHub repository `tristanpeto123-eng/Agentic-Trading`, branch `main`. Build using the root `Dockerfile` and use healthcheck path `/health`.
3. Attach a persistent volume at **/data** to retain the SQLite database and quarantined CSV uploads between deployments. Keep one web replica.
4. Set variables: `APP_ENV=production`, `DATABASE_URL=sqlite:////data/agentic.sqlite3`, `DATA_STORAGE_DIR=/data/data_store`, a unique randomly generated **SESSION_SECRET** (at least 32 characters), **PREVIEW_SETUP_TOKEN** (at least 40 characters), and `ALLOWED_ORIGINS=https://<exact-issued-railway-hostname>`. Never commit or publish secrets or provider CSV files.
5. Generate the Railway service's HTTPS domain and update `ALLOWED_ORIGINS` to its **exact origin** (no trailing slash). Wait for deployment healthcheck to pass.
6. Open `https://<your-domain>/setup` in Safari. Enter your own email and a unique 12+ character password plus the one-time setup code. The setup endpoint accepts only requests originating from your configured preview domain and refuses all further CEO creations once one exists.
7. Return to `/`, log in and evaluate Home, Students and Trading. The app is **password-protected but the login page is internet-facing**. Do not put private trading records into a public repository.
8. After creating the CEO, remove `PREVIEW_SETUP_TOKEN` from Railway variables. Existing CEO login continues working; the setup endpoint then returns disabled/initialised.

## Run, rollback and safety

- The container runs Alembic migrations at startup and serves frontend and API from **one origin** for CSRF and secure HttpOnly cookies.
- Do **not** use Railway's ephemeral disk for SQLite. Losing the attached volume loses the preview's stored accounts/students. Back up before any migration or volume removal.
- The current SQLite/volume arrangement is a **single-replica demonstration** only, not a horizontally scaled or highly available service.
- Offline neural network training requires a separately provisioned worker and CPU PyTorch; it does not execute automatically here. Empty student training reports are expected.
- All imports remain quarantined. Model qualification and paper/live trading are disabled; a CEO setup or readiness request does not alter those gates.
- To remove public access, delete the service domain in Railway (or stop the service). Inspect Railway logs for failures; avoid posting secrets in chats, issues or screenshots.
- Railway usage may incur charges according to the account's plan; inspect resource usage and billing before leaving services running.

Evaluation is **not** evidence of trading performance, security accreditation or a deployable trading product. See `docs/PROGRAM_END_REVIEW.md` for outstanding gates.
