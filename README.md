# Agentic Trading

Independent, research-first academy for named AI trading students. **Sprint 1 implements CEO login, mobile-first Home / Students / Trading UI, unique student creation and persistent versioned learning plans.** There is no market-data pipeline, ML training, broker connection, actual or simulated order execution, financial performance data, or qualification engine yet.

**The GitHub repository is public by the owner's choice. Source code is public; the CEO interface is password-protected and is not deployed. Never commit credentials, account data, student private histories or market-data purchases.**

## Sprint 1 — run locally

Requires Python 3.11+ and Node.js 20+. Use two terminals.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e './backend[dev]'

# Set DATABASE_URL and SESSION_SECRET for the current shell (or use dev defaults).
cd backend
alembic -c alembic.ini upgrade head
cd ..

# First-time only; enter a 12+ character CEO password interactively (not in code or CLI args).
python -m agentic_trading.bootstrap_ceo --email you@example.com
uvicorn agentic_trading.api:app --host 127.0.0.1 --port 8000 --reload
```

In terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173** in your browser and log in using the CEO credentials you created. The backend is reached through the Vite proxy so the HttpOnly signed cookie stays same-origin. Database URL defaults to a local SQLite file, **relative to the process working directory**; run migrations, bootstrap and API using the same directory or set an absolute `DATABASE_URL`.

Run checks:

```bash
python -m pytest backend/tests -q
cd frontend && npm run build
```

`pip install -e './backend[dev,postgres]'` includes PostgreSQL driver; use `DATABASE_URL=postgresql+psycopg://...` and run Alembic migrations before deploying. Production also requires HTTPS, fixed `SESSION_SECRET`, approved origins, multi-worker throttling, backups, operational monitoring and security review. **Don't put this dev server on the public internet.**

## Sprint 1 functionality

- CEO account bootstrap, Argon2-hashed password, signed eight-hour HttpOnly session, server-verified CEO role, CSRF protection for writes, basic rate limiting and origin checks.
- Students with UUID identity, normalized/case-insensitive unique names and persistent enrollments.
- Autonomous or CEO-directed research plans; directed targets require a market and a skill. Any direction change records a new immutable plan version. Rename preserves ID and plan history.
- Audit events for creation, rename and direction changes.
- Mobile-first console with working login, student creation, student profile, change direction, Home summary and three explicitly segregated disabled Trading modes.
- Alembic initial database migration (SQLite dev and PostgreSQL schema), automated API/permission/persistence/migration tests and CI frontend TypeScript build.

## Safety and architecture

Every new student is **unqualified**, **not training**, **not trading**. Learning targets are not earned skills; research grading and student promotion remain future work. No trading modes can be enabled through this API. The existing [governance policy](docs/PRODUCT_SPEC_v1.0.md) remains locked.

[Product specification](docs/PRODUCT_SPEC_v1.0.md) · [Sprint tracker](docs/SPRINTS.md) · [Security](docs/SECURITY.md) · [Sprint 1 verification](docs/SPRINT1_CHECK.md).

Entirely independent of Scalp City: no shared imports, datasets, credentials, models or repository dependencies.
