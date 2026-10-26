# Agentic Trading

Independent, research-first academy for named AI trading students. **Sprint 1 is merged. Sprint 2 adds research-only XAUUSD M15 CSV import, immutable raw/normalized files, structural quality reports, historical context queries and an import panel under Home.** No real provider has been connected or approved; all imports remain quarantined. There is no ML training, broker connection, order execution, financial performance data, or qualification engine yet.

**The GitHub repository is public by the owner's choice. Source code is public; the CEO interface is password-protected and is not deployed. Never commit credentials, account data, student private histories or market-data purchases.**

## Sprint 2 — run locally

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

## Sprint 1 and 2 functionality

- CEO account bootstrap, Argon2-hashed password, signed eight-hour HttpOnly session, server-verified CEO role, CSRF protection for writes, basic rate limiting and origin checks.
- Students with UUID identity, normalized/case-insensitive unique names and persistent enrollments.
- Autonomous or CEO-directed research plans; directed targets require a market and a skill. Any direction change records a new immutable plan version. Rename preserves ID and plan history.
- Audit events for creation, rename and direction changes.
- Mobile-first console with working login, student creation, student profile, change direction, Home summary and three explicitly segregated disabled Trading modes.
- Alembic initial database migration (SQLite dev and PostgreSQL schema), automated API/permission/persistence/migration tests and CI frontend TypeScript build.

## Sprint 2 data pipeline

Home → Data Engine → Import CSV accepts 12 MiB maximum of UTC M15 XAUUSD candles (up to 80,000). Record a real provider HTTPS URL, extraction reference, usage-rights reference and price basis. The server saves immutable SHA-256-labelled raw CSV and normalized JSONL outside Git, detects input errors and data gaps, and serves completed-only H1/H4 context for a historical `as_of` time. **Source authenticity and legal permissions are not automatically established: all imports are quarantined and prohibited from qualification.**

To keep source files on persistent private storage, set `DATA_STORAGE_DIR` in `.env`/shell. `data_store/` is the default if unset. Read [Data Import Guide](docs/DATA_IMPORT.md) and [Sprint 2 Review](docs/SPRINT2_CHECK.md).

## Safety and architecture

Every new student is **unqualified**, **not training**, **not trading**. Learning targets are not earned skills; research grading and student promotion remain future work. No trading modes can be enabled through this API. The existing [governance policy](docs/PRODUCT_SPEC_v1.0.md) remains locked.

[Product specification](docs/PRODUCT_SPEC_v1.0.md) · [Sprint tracker](docs/SPRINTS.md) · [Security](docs/SECURITY.md) · [Sprint 1 verification](docs/SPRINT1_CHECK.md).

Entirely independent of Scalp City: no shared imports, datasets, credentials, models or repository dependencies.

### Dukascopy research data adapter (Sprint 2 follow-up)

The optional `scripts/fetch_dukascopy_xauusd.py` script downloads or offline-processes
provider M1 BID/ASK archives into separated M15 CSVs with per-file SHA-256
provenance. Downloading requires `--download` and valid permitted access; it
is not enabled by default. **No real provider export or licence has been validated**;
all imported CSV files remain quarantined. See `docs/DATA_IMPORT.md`.

## Sprint 3 — historical replay research engine (review branch)

The optional `agentic_trading.simulator` module replays guarded XAUUSD research instructions against **genuine bid/ask M1-shaped inputs**; its included fixtures are explicitly synthetic. It models spread, two commissions, adverse slippage, stop/target conservatism, gap losses, expiry, missing data, risk limits, immutable ledger records and reproducible fingerprints. No browser/API trading endpoint has been added. To see a synthetic-only smoke demonstration, run `python scripts/demo_historical_replay.py`. Read [Replay Rules](docs/HISTORICAL_REPLAY.md) and [Sprint 3 Review](docs/SPRINT3_CHECK.md). The S2 provenance gate remains open and no unverified import is permitted to qualify a student.


## Sprint 4 — offline intelligence pipeline (review branch)

`agentic_trading.intelligence` adds deterministic Scout A regime analysis,
Strategist B trend/breakout/range proposals, empirical closed-trade Scout B scoring,
mandatory Guardian research-only risk vetos and observation-only thesis monitoring.
The optional handoff to Sprint 3 accepts Guardian-approved **historical research**
intents; there are no broker, paper/live or student qualification endpoints.
Neither Scout A nor Scout B is a trained neural model yet (see S6).
Run `python scripts/demo_research_intelligence.py` for **synthetic-only** output.
Read [Intelligence Rules](docs/TRADING_INTELLIGENCE.md) and
[Sprint 4 Checker Report](docs/SPRINT4_CHECK.md).

## Sprint 5 — Skill Library and research memory (draft)

The proposed S5 branch adds a versioned Skill Library (`GET /v1/skills/catalog`), student skill-progress summaries and a closed-trade Good/Bad/Flat episode archive at `GET /v1/students/{id}/memory`. Every archived outcome is derived from net P&L after spread, slippage and fees, with full source/proposal hashes and UTC time visibility. The internal recall function only retrieves **training-partition** experiences available before a decision time, and always remains per student. Synthetic and quarantined episodes **do not qualify** real trading ability. See `docs/SKILLS_MEMORY.md`.

No neural training workers, broker access or paper/live trading are enabled. The independent Examiner is not yet implemented.

## Sprint 6 — offline neural research (review)

CPU PyTorch neural baseline and restartable/checksum-verified training now live **in code only**; no automatic jobs, model qualifications or broker operations. See [`docs/NEURAL_TRAINING.md`](docs/NEURAL_TRAINING.md), `docs/SPRINT6_CHECK.md` and `scripts/train_student_offline.py`. Training history is visible in Students → selected student → Training; blank until an offline worker has suitable closed research episodes. Synthetic/quarantined data is never evidence of profitability.

## Sprint 7 — Independent Examiner (research prototype)

A deterministic, offline historical Examiner computes challenger-versus-incumbent/cash-baseline results on common M1 bid/ask and costs. The authenticated Student Exams view exposes immutable reports and explicit provenance limitations. See [`docs/INDEPENDENT_EXAMINER.md`](docs/INDEPENDENT_EXAMINER.md). No independently qualified research, broker connectivity, paper or live trading exists. S2 licensing and verified 12-month XAUUSD data remain outstanding.

## Sprint 8 research Academy

The **offline Academy scheduler** uses bounded, durable idempotent lessons and jobs. Because no verified XAUUSD source exists, normal jobs remain blocked; fixture-only tests never grant research qualification or trading authority. See `docs/ACADEMY.md` and `docs/SPRINT8_CHECK.md`.
