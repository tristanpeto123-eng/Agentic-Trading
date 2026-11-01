"""Sprint 1 CEO app. No broker, order execution or model-training routes exist."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import os
import json
import time

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from agentic_trading import __version__
from agentic_trading.data_engine import (DatasetImport, DataQualityError, ingest_csv, frozen_bytes,
                                        load_candles, completed_aggregates, parse_iso_utc)
from agentic_trading.auth import (
    SESSION_COOKIE, SESSION_SECONDS, csrf_token, csrf_valid, make_session, read_session, verify_password
)
from agentic_trading.schemas import (
    ChangeDirection, CreateStudent, LearningMode, LoginRequest, RenameStudent,
    StudentResponse, name_key,
)
from agentic_trading.skills_memory import catalog_manifest, read_student_memory, student_skill_progress, MemoryError
from agentic_trading.neural_training import student_training_runs, TrainingError
from agentic_trading.examiner import student_exam_history, ExaminationError
from agentic_trading.academy import lesson_plan, student_jobs, AcademyError
from agentic_trading.policy_checkpoint import research_policy_history, PolicyResearchError
from agentic_trading.evolution import student_evolution, peer_lessons, mentorship_eligibility, EvolutionError
from agentic_trading.evolution_tower import (
    initial_state as initial_tower, advance_state as advance_tower,
    public_state as public_tower, _digest as tower_digest, TowerError,
)
from agentic_trading.sentinel import scan_health, engage_stop, safety_latch, SentinelError
from agentic_trading.paper_readiness import evaluate_readiness, paper_requests, PaperReadinessError
from agentic_trading.providers.alpaca_paper_readonly import preview_btc_paper, PaperPreviewError
from agentic_trading.providers.alpaca_account_readonly import read_paper_account, PaperAccountReadError
from agentic_trading.providers.alpaca_crypto_history import fetch_private_btc_history, CryptoDataError
from agentic_trading.providers.xauusd_bidask import (
    QuoteSourceError, fetch_oanda_practice, fetch_dukascopy_research, compare_sources,
)
from agentic_trading.settings import Settings
from agentic_trading.historical_store import DATABASE_ARTIFACT_PATH, store_historical_artifacts, verified_candles
from agentic_trading.historical_demo import build_historical_demo
from agentic_trading.candle_study import study_candles, CandleStudyError
from agentic_trading.m15_trade_scenario import study_costed_outcomes
from agentic_trading.research_trace import TraceBatchInput, NeuralPredictionInput, inspect_trace_batch
from agentic_trading.research_neural import (create_run as start_neural_run, train_one_epoch,
    get_run_report, load_neural_inference, score_neural_candidate, ResearchNeuralError, MODEL_SCHEMA)
from agentic_trading.storage import AuditEvent, Base, CEO, LearningPlan, Student, HistoricalDataset, ResearchNeuralRun, EvolutionTowerSession, EvolutionTowerArchive, new_session_factory


class LoginLimiter:
    """Basic in-process throttling; use upstream distributed throttling for deployments."""
    def __init__(self):
        self.attempts: dict[str, deque] = defaultdict(deque)

    def check(self, key: str):
        now = time.monotonic()
        queue = self.attempts[key]
        while queue and now - queue[0] > 300:
            queue.popleft()
        if len(queue) >= 5:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        queue.append(now)

    def clear(self, key: str):
        self.attempts.pop(key, None)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    engine, session_factory = new_session_factory(cfg.database_url)
    # Database schema is managed with Alembic; start with `alembic upgrade head`.
    limiter = LoginLimiter()
    data_root = Path(cfg.data_dir) if cfg.data_dir else Path.cwd() / "data_store"
    postgres_archive = cfg.database_url.startswith("postgresql+")
    historical_upload_available = (os.environ.get("HISTORICAL_UPLOADS_FORCE_DISABLED") != "1" and
        (postgres_archive or os.environ.get("PREVIEW_DISABLE_IMPORTS", "") != "1"))
    api = FastAPI(title="Agentic Trading", version=__version__, description="CEO + student foundation. Trading remains disabled.")
    api.add_middleware(
        CORSMiddleware, allow_origins=list(cfg.allowed_origins), allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    def db():
        with session_factory() as session:
            yield session

    def ensure_origin(request: Request):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in cfg.allowed_origins:
                raise HTTPException(status_code=403, detail="Origin not permitted")
            # An actual browser cannot add this custom header cross-origin without preflight.
            if request.method != "GET" and request.headers.get("sec-fetch-site") == "cross-site":
                raise HTTPException(status_code=403, detail="Cross-site request rejected")

    def current_ceo(request: Request, session: Session = Depends(db)) -> tuple[CEO, dict]:
        cookie = request.cookies.get(SESSION_COOKIE)
        claims = read_session(cfg.secret_key, cookie) if cookie else None
        if claims is None:
            raise HTTPException(status_code=401, detail="CEO login required")
        user = session.get(CEO, claims["sub"])
        if user is None or user.role != "ceo":
            raise HTTPException(status_code=401, detail="CEO login required")
        return user, claims

    def require_csrf(request: Request, ceo_info: tuple[CEO, dict] = Depends(current_ceo)) -> CEO:
        ensure_origin(request)
        if not csrf_valid(cfg.secret_key, ceo_info[1]["nonce"], request.headers.get("x-csrf-token")):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")
        return ceo_info[0]

    def get_student_or_404(student_id: str, session: Session) -> Student:
        student = session.scalar(select(Student).options(selectinload(Student.plans)).where(Student.id == student_id))
        if student is None:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    def output(student: Student, *, full: bool = False) -> StudentResponse:
        versions = sorted(student.plans, key=lambda x: x.version)
        return StudentResponse(
            id=student.id, name=student.name, status=student.status,
            created_at=student.created_at, updated_at=student.updated_at,
            learning_plan=versions[-1], plan_history=versions if full else None,
            training_active=False, qualification="unqualified",
        )

    @api.get("/health")
    def health():
        return {"status": "ok", "component": "api", "sprint": "S11"}

    def _read_tower(session: Session, ceo_id: str, *, locked: bool = False):
        query = select(EvolutionTowerSession).where(EvolutionTowerSession.ceo_id == ceo_id)
        if locked:
            query = query.with_for_update()
        record = session.scalar(query)
        if record is not None and record.state_sha256 != tower_digest(record.state):
            raise HTTPException(status_code=409, detail="Evolution Tower state integrity mismatch")
        return record

    def _tower_events(session: Session, session_id: str) -> list[dict]:
        records = session.scalars(
            select(EvolutionTowerArchive)
            .where(EvolutionTowerArchive.session_id == session_id)
            .order_by(EvolutionTowerArchive.generation.desc()).limit(20)
        ).all()
        if any(event.event_sha256 != tower_digest(event.event) for event in records):
            raise HTTPException(status_code=409, detail="Evolution archive integrity mismatch")
        return [record.event for record in records]

    @api.get("/v1/evolution-tower")
    def get_evolution_tower(response: Response,
                            ceo_info: tuple[CEO, dict] = Depends(current_ceo),
                            session: Session = Depends(db)):
        response.headers["Cache-Control"] = "no-store"
        record = _read_tower(session, ceo_info[0].id)
        if record is None:
            return {"initialized": False, "research_only": True, "paper_trading_enabled": False,
                    "live_trading_enabled": False, "penthouse_locked": True,
                    "population_size": 16}
        return {"initialized": True, "research_only": True,
                **public_tower(record.state, _tower_events(session, record.id)),
                "state_sha256": record.state_sha256}

    @api.post("/v1/evolution-tower/start")
    def start_evolution_tower(response: Response, _: CEO = Depends(require_csrf),
                             session: Session = Depends(db)):
        """Create one durable research cohort, never overwrite existing chromosomes."""
        record = _read_tower(session, _.id, locked=True)
        if record is None:
            state = initial_tower()
            record = EvolutionTowerSession(
                ceo_id=_.id, generation=0, state=state, state_sha256=tower_digest(state))
            session.add(record)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise HTTPException(status_code=409,
                                    detail="Evolution cohort was already initialized; refresh") from exc
        response.headers["Cache-Control"] = "no-store"
        return {"initialized": True, "research_only": True,
                **public_tower(record.state, _tower_events(session, record.id)),
                "state_sha256": record.state_sha256}

    @api.post("/v1/evolution-tower/advance")
    def step_evolution_tower(payload: dict, response: Response,
                            ceo: CEO = Depends(require_csrf),
                            session: Session = Depends(db)):
        """One bounded generation per request, never runs or connects a broker."""
        if set(payload) != {"expected_generation"} or type(payload.get("expected_generation")) is not int:
            raise HTTPException(status_code=422, detail="Expected generation integer required")
        record = _read_tower(session, ceo.id, locked=True)
        if record is None:
            raise HTTPException(status_code=409, detail="Create research cohort first")
        if payload["expected_generation"] != record.generation:
            raise HTTPException(status_code=409, detail="Generation changed; reload authoritative tower state")
        try:
            updated, events = advance_tower(record.state)
        except TowerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        event = events[0]
        record.state = updated
        record.state_sha256 = tower_digest(updated)
        record.generation = updated["generation"]
        record.updated_at = datetime.now(timezone.utc)
        session.add(EvolutionTowerArchive(
            session_id=record.id, generation=record.generation,
            event=event, event_sha256=tower_digest(event)))
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409,
                                detail="Concurrent generation already committed") from exc
        response.headers["Cache-Control"] = "no-store"
        return {"initialized": True, "research_only": True,
                **public_tower(updated, _tower_events(session, record.id)),
                "state_sha256": record.state_sha256}

    @api.get("/v1/capabilities")
    def capabilities():
        return {
            "name": "Agentic Trading", "stage": "sprint_11_paper_readiness",
            "research_training_enabled": False, "historical_execution_enabled": False,
            "paper_trading_enabled": False, "live_trading_enabled": False,
            "broker_connected": False, "student_creation_enabled": True,
            "historical_data_import_enabled": historical_upload_available, "historical_research_enabled": True, "historical_candle_replay_enabled": True, "historical_candle_study_enabled": True, "historical_synthetic_demo_enabled": True, "research_data_qualified": False,
            "skills_catalog_enabled": True, "episodic_memory_read_enabled": True,
            "independent_skill_mastery_enabled": False, "automatic_memory_ingest_enabled": False,
            "offline_neural_research_training_available": True, "automatic_training_enabled": False,
            "evolution_tower_synthetic_demo_enabled": True, "evolution_tower_background_worker_enabled": False,
            "incremental_persistent_neural_research_enabled": True, "research_checkpoint_database_backed": True,
            "independent_examiner_enabled": False,
            "offline_research_examiner_available": True, "academy_scheduler_available": True, "strategy_dna_read_enabled": True, "peer_research_lessons_enabled": True, "sentinel_read_enabled": True, "emergency_stop_enabled": True, "paper_readiness_report_enabled": True, "paper_account_readonly_available": True, "independent_examination_qualification_enabled": False,
        }

    @api.post("/v1/auth/login")
    def login(payload: LoginRequest, request: Request, response: Response, session: Session = Depends(db)):
        ensure_origin(request)
        email = payload.email.strip().casefold()
        key = f"{request.client.host if request.client else 'unknown'}:{email}"
        limiter.check(key)
        user = session.scalar(select(CEO).where(CEO.email == email))
        if user is None or not verify_password(user.password_hash, payload.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        limiter.clear(key)
        cookie, csrf = make_session(cfg.secret_key, user.id)
        response.set_cookie(SESSION_COOKIE, cookie, max_age=SESSION_SECONDS, httponly=True,
                            secure=cfg.cookie_secure, samesite="strict", path="/")
        return {"email": user.email, "role": "ceo", "csrf_token": csrf}

    @api.get("/v1/auth/me")
    def me(ceo_info: tuple[CEO, dict] = Depends(current_ceo)):
        user, claims = ceo_info
        return {"email": user.email, "role": "ceo", "csrf_token": csrf_token(cfg.secret_key, claims["nonce"])}

    @api.post("/v1/auth/logout")
    def logout(response: Response, _: CEO = Depends(require_csrf)):
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    @api.get("/v1/dashboard")
    def dashboard(_: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        total = session.scalar(select(func.count(Student.id))) or 0
        count = session.scalar(select(func.count(HistoricalDataset.id))) or 0
        return {
            "students_total": total, "historical_datasets_total": count, "students_training": 0, "research_qualified": 0,
            "research_status": "not_started", "market_data_status": "imports_quarantined" if count else "not_connected",
            "historical_research": "available", "historical_trading": "disabled", "paper_trading": "disabled",
            "live_trading": "disabled", "system_health": "api_online",
            "net_pnl": None, "open_positions": None,
            "attention": ["Historical imports require independent provider/rights verification before training"],
        }

    def dataset_view(row: HistoricalDataset) -> dict:
        return {"id": row.id, "instrument": row.source_manifest["instrument"],
                "timeframe": row.source_manifest["timeframe"], "provider": row.source_manifest["provider"],
                "source_hash": row.source_hash, "canonical_hash": row.canonical_hash,
                "source_manifest": row.source_manifest, "quality_report": row.quality_report,
                "state": row.state, "research_eligible": False, "ingested_at": row.ingested_at}

    @api.get("/v1/historical/demo")
    def historical_demo(_: tuple[CEO, dict] = Depends(current_ceo)):
        """Offline fixture replay only: no orders placed and no qualified market evidence."""
        return build_historical_demo()

    @api.get("/v1/research/market-history")
    def research_market_history(days: int = 14, response: Response = None,
                                _: tuple[CEO, dict] = Depends(current_ceo)):
        """Import fully completed BTC/USD M15 candles using public, GET-only Alpaca data.

        No broker account credentials or orders, training, database writes,
        model advancement or qualification. User requested private research import.
        """
        if days not in (7, 14, 30):
            raise HTTPException(status_code=422, detail="Choose 7, 14 or 30 days")
        instant = datetime.now(timezone.utc)
        end = instant.replace(minute=(instant.minute // 15) * 15,
                              second=0, microsecond=0)
        try:
            snapshot = fetch_private_btc_history(
                start=end - timedelta(days=days), end=end,
                now=instant, timeframe="15Min", kind="bars",
                allow_network=True, private_research_acknowledged=True,
            )
            values = [json.loads(line) for line in snapshot.canonical_jsonl.splitlines()]
            if len(values) < 80:
                raise CryptoDataError("Insufficient completed BTC/USD M15 bars")
            output = []
            previous = None
            gaps = 0
            for row in values:
                dt = parse_iso_utc(row["t"])
                if previous is not None and dt - previous != timedelta(minutes=15):
                    gaps += 1
                previous = dt
                output.append({
                    "open_time": dt.isoformat().replace("+00:00", "Z"),
                    "available_at": (dt + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
                    "open": row["o"], "high": row["h"], "low": row["l"],
                    "close": row["c"], "volume": row["v"],
                })
        except (CryptoDataError, DataQualityError, ValueError, KeyError, TypeError):
            raise HTTPException(status_code=503, detail="Alpaca historical feed unavailable or failed data integrity checks") from None
        response.headers["Cache-Control"] = "no-store"
        return {
            "symbol": "BTCUSD", "market": "BTC/USD", "timeframe": "M15",
            "provider": "Alpaca public crypto bars",
            "source_url": snapshot.report["source_endpoint"],
            "source_sha256": snapshot.report["canonical_sha256"],
            "bars": output, "gap_count": gaps, "rows": len(output),
            "source_verified": False, "price_basis": "aggregate",
            "research_eligible": False, "historical_execution_enabled": False,
            "paper_trading_enabled": False, "live_trading_enabled": False,
            "persisted": False, "model_training_performed": False,
            "note": "Private research-only imported BTC M15 aggregates. Not saved, broker fills, executable quotes, neural training or approved trading. Provider conditions still apply.",
        }

    @api.get("/v1/students/{student_id}/neural/latest")
    def latest_research_neural(student_id: str, response: Response,
                             _: tuple[CEO, dict] = Depends(current_ceo),
                             session: Session = Depends(db)):
        get_student_or_404(student_id, session)
        response.headers["Cache-Control"] = "no-store"
        try:
            return {"run": get_run_report(session, student_id)}
        except ResearchNeuralError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/v1/students/{student_id}/neural/start")
    def start_research_neural(student_id: str, response: Response,
                            user: CEO = Depends(require_csrf),
                            session: Session = Depends(db)):
        """One click: resume frozen evidence or import new history and start an experiment.

        CPU-only, no broker route, no trading qualification. Browser drives one
        bounded epoch per request; every epoch persists before next request.
        """
        student = get_student_or_404(student_id, session)
        try:
            saved = get_run_report(session, student_id)
        except ResearchNeuralError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        plan = max(student.plans, key=lambda row: row.version)
        if (saved is not None and saved["state"] != "complete"
                and saved["model_schema"] == MODEL_SCHEMA):
            frozen_run = session.get(ResearchNeuralRun, saved["run_id"])
            if frozen_run.plan_version != plan.version:
                raise HTTPException(status_code=409, detail="Saved neural run uses an older student learning plan; CEO review required")
            response.headers["Cache-Control"] = "no-store"
            return saved
        permitted = ("trend", "range", "breakout") if plan.mode == "autonomous" else (
            tuple(skill for skill in ("trend", "range", "breakout") if skill in plan.skills))
        if not permitted:
            raise HTTPException(status_code=409, detail="Student has no supported research strategy")
        # Reuse the verified student/source selection path. Its response is
        # unqualified by design. It reads no model or order credentials.
        selection = student_training_source(student_id, response, (user, {}), session)
        try:
            result = start_neural_run(
                session, student_id,
                market=selection["market"], tactic=permitted[0],
                plan_version=plan.version, bars=selection["bars"],
                source_sha256=selection["source_sha256"],
            )
        except ResearchNeuralError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        response.headers["Cache-Control"] = "no-store"
        return result

    @api.post("/v1/students/{student_id}/neural/{run_id}/epoch")
    def advance_research_neural(student_id: str, run_id: str, payload: dict,
                                response: Response, _: CEO = Depends(require_csrf),
                                session: Session = Depends(db)):
        """Idempotence guarded by expected_epoch; no file writes or broker orders."""
        student = get_student_or_404(student_id, session)
        record = session.get(ResearchNeuralRun, run_id)
        if record is not None and record.student_id == student_id:
            if record.plan_version != max(p.version for p in student.plans):
                raise HTTPException(status_code=409, detail="Student learning plan changed; frozen neural run cannot advance")
        if set(payload) != {"expected_epoch"} or type(payload.get("expected_epoch")) is not int:
            raise HTTPException(status_code=422, detail="Expected numeric epoch required")
        if not 0 <= payload["expected_epoch"] < 80:
            raise HTTPException(status_code=422, detail="Epoch out of bounds")
        try:
            report = train_one_epoch(session, student_id, run_id, payload["expected_epoch"])
        except ResearchNeuralError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        response.headers["Cache-Control"] = "no-store"
        return report

    @api.get("/v1/students/{student_id}/train-data")
    def student_training_source(student_id: str, response: Response,
                                _: tuple[CEO, dict] = Depends(current_ceo),
                                session: Session = Depends(db)):
        """Choose student market and import research-only history on button press.

        This supplies candle-by-candle training *simulation* inputs, not
        S6 neural examples or broker orders. No database or student writes.
        """
        student = get_student_or_404(student_id, session)
        plan = max(student.plans, key=lambda item: item.version)
        targets = list(plan.markets) if plan.mode == "directed" else ["XAUUSD", "BTCUSD"]
        # Remote XAU research is opt-in; neither feed authorises order routing.
        provider_failures = []
        if "XAUUSD" in targets:
            oanda_enabled = os.environ.get("ATL_OANDA_PRACTICE_RESEARCH", "0") == "1"
            dukascopy_enabled = os.environ.get("ATL_DUKASCOPY_RESEARCH_DOWNLOAD", "0") == "1"
            snapshot = None
            if oanda_enabled:
                try:
                    snapshot = fetch_oanda_practice(token=os.environ.get("OANDA_V20_PRACTICE_TOKEN", ""))
                except QuoteSourceError as exc:
                    provider_failures.append(str(exc))
            if dukascopy_enabled and (snapshot is None or
                    os.environ.get("ATL_XAU_CROSSCHECK", "0") == "1"):
                try:
                    dukascopy = fetch_dukascopy_research(
                        cache_dir=data_root / "dukascopy-cache", download=True)
                    if snapshot is None:
                        snapshot = dukascopy
                    else:
                        snapshot["crosscheck"] = compare_sources(snapshot, dukascopy)
                except QuoteSourceError as exc:
                    provider_failures.append(str(exc))
                    if snapshot is not None:
                        snapshot["crosscheck"] = {"comparable": False, "reason": "secondary feed unavailable"}
            if snapshot is not None:
                response.headers["Cache-Control"] = "no-store"
                return {"student_id": student_id, **snapshot}
        if "XAUUSD" in targets:
            rows = session.scalars(select(HistoricalDataset).order_by(
                HistoricalDataset.ingested_at.desc())).all()
            for source in rows:
                if (source.state == "quarantined" and
                    source.source_manifest.get("instrument") == "XAUUSD" and
                    source.source_manifest.get("timeframe") == "M15"):
                    try:
                        candles = [x for x in verified_candles(session, source, data_root)
                                   if x.available_at <= datetime.now(timezone.utc)]
                    except (DataQualityError, OSError, ValueError):
                        raise HTTPException(status_code=409, detail="Saved XAUUSD history failed integrity verification") from None
                    if len(candles) >= 80:
                        bars = [x.as_dict() for x in candles[-2016:]]
                        response.headers["Cache-Control"] = "no-store"
                        return {
                            "student_id": student_id, "market": "XAUUSD",
                            "provider": source.source_manifest.get("provider", "Owner archive"),
                            "source_sha256": source.canonical_hash,
                            "bars": bars,
                            "gap_count": sum(parse_iso_utc(b["open_time"])-parse_iso_utc(a["open_time"]) != timedelta(minutes=15)
                                              for a,b in zip(bars, bars[1:])),
                            "source_verified": False, "training_kind": "historical_policy_replay",
                            "neural_training_performed": False,
                            "persisted": False, "paper_trading_enabled": False, "live_trading_enabled": False,
                            "note": "Automatically selected existing owner archive; no executable quote or model qualification.",
                        }
        if "BTCUSD" in targets:
            instant = datetime.now(timezone.utc)
            end = instant.replace(minute=(instant.minute // 15) * 15,
                                  second=0, microsecond=0)
            try:
                snapshot = fetch_private_btc_history(
                    start=end - timedelta(days=14), end=end,
                    now=instant, timeframe="15Min", kind="bars",
                    allow_network=True, private_research_acknowledged=True)
                records = [json.loads(line) for line in snapshot.canonical_jsonl.splitlines()]
                if len(records) < 80:
                    raise CryptoDataError("Insufficient public BTC history")
                bars = [
                    {"open_time": parse_iso_utc(row["t"]).isoformat().replace("+00:00", "Z"),
                     "available_at": (parse_iso_utc(row["t"]) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
                     "open": row["o"], "high": row["h"], "low": row["l"],
                     "close": row["c"], "volume": row["v"]}
                    for row in records
                ]
            except (CryptoDataError, ValueError, KeyError, TypeError):
                raise HTTPException(status_code=503, detail="BTC/USD historical feed unavailable; research training cannot start") from None
            response.headers["Cache-Control"] = "no-store"
            return {
                "student_id": student_id, "market": "BTCUSD",
                "provider": "Alpaca public historical crypto bars",
                "source_sha256": snapshot.report["canonical_sha256"],
                "bars": bars,
                "gap_count": sum(parse_iso_utc(b["open_time"])-parse_iso_utc(a["open_time"]) != timedelta(minutes=15)
                                  for a,b in zip(bars, bars[1:])),
                "source_verified": False, "training_kind": "historical_policy_replay",
                "neural_training_performed": False,
                "persisted": False, "paper_trading_enabled": False, "live_trading_enabled": False,
                "note": "Public BTC aggregates; some prices use quote midpoints. Hypothetical research, not qualified or executed trades.",
            }
        raise HTTPException(
            status_code=409,
            detail=("XAUUSD source unavailable: " + "; ".join(provider_failures)
                    if provider_failures and targets == ["XAUUSD"] else
                    "No automatic historical feed available for this student's target market. "
                    "Enable an approved XAU/USD OANDA practice or Dukascopy source, or add an owner archive. "
                    "Other markets require a separate read-only provider."),
        )

    @api.get("/v1/datasets")
    def datasets(_: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        return [dataset_view(row) for row in session.scalars(
            select(HistoricalDataset).order_by(HistoricalDataset.ingested_at.desc(), HistoricalDataset.id.desc())
        ).all()]

    @api.post("/v1/datasets/import", status_code=201)
    def import_dataset(payload: DatasetImport, user: CEO = Depends(require_csrf), session: Session = Depends(db)):
        if not historical_upload_available:
            raise HTTPException(status_code=503, detail="Historical import requires durable PostgreSQL storage on this free preview.")
        content = payload.csv_content.encode("utf-8")
        digest = sha256(content).hexdigest()
        manifest = payload.source.model_dump(mode="json")
        existing = session.scalar(select(HistoricalDataset).where(HistoricalDataset.source_hash == digest))
        if existing is not None:
            if existing.source_manifest != manifest:
                raise HTTPException(status_code=409, detail="Identical raw CSV already imported with different provenance")
            return dataset_view(existing)
        try:
            candles, quality, canonical = ingest_csv(payload.csv_content, payload.source.acquired_at)
            if postgres_archive:
                raw_path = canonical_path = DATABASE_ARTIFACT_PATH
            else:
                raw_path, canonical_path = frozen_bytes(data_root, digest, content, canonical)
        except (DataQualityError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row = HistoricalDataset(source_hash=digest, canonical_hash=sha256(canonical).hexdigest(),
                                source_manifest=manifest, quality_report=quality,
                                raw_path=raw_path, canonical_path=canonical_path,
                                state="quarantined")
        session.add(row)
        try:
            session.flush()
            if postgres_archive:
                store_historical_artifacts(session, row.id, content, canonical)
            session.add(AuditEvent(actor_id=user.id, action="dataset.imported", subject_id=row.id,
                                   detail={"source_hash": digest, "rows": len(candles), "state": "quarantined"}))
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Dataset already imported concurrently") from exc
        return dataset_view(row)

    @api.get("/v1/datasets/{dataset_id}")
    def dataset_detail(dataset_id: str, _: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        row = session.get(HistoricalDataset, dataset_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return dataset_view(row)

    @api.get("/v1/datasets/{dataset_id}/context")
    def historical_context(dataset_id: str, as_of: str, _: tuple[CEO, dict] = Depends(current_ceo),
                           session: Session = Depends(db)):
        row = session.get(HistoricalDataset, dataset_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        try:
            now = parse_iso_utc(as_of)
            candles = verified_candles(session, row, data_root)
        except (DataQualityError, OSError) as exc:
            raise HTTPException(status_code=409, detail=f"Data integrity check failed: {exc}") from exc
        eligible = [c for c in candles if c.available_at <= now]
        h1 = completed_aggregates(candles, now, 60)
        h4 = completed_aggregates(candles, now, 240)
        return {"dataset_id": row.id, "as_of": now, "research_eligible": False,
                "m15": [x.as_dict() for x in eligible[-16:]], "h1": h1[-8:], "h4": h4[-4:],
                "note": "Only completed candles are visible. This quarantined dataset cannot qualify research."}

    @api.get("/v1/datasets/{dataset_id}/candles")
    def research_candles(dataset_id: str, limit: int = 240, before: str | None = None,
                         _: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        """Time-safe, checksum-verified M15 candle playback, NOT order simulation."""
        if not 20 <= limit <= 360:
            raise HTTPException(status_code=422, detail="Candle page size must be 20-360")
        row = session.get(HistoricalDataset, dataset_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        try:
            cutoff = parse_iso_utc(before) if before else None
            candles = verified_candles(session, row, data_root)
        except (DataQualityError, OSError) as exc:
            raise HTTPException(status_code=409, detail=f"Data integrity check failed: {exc}") from exc
        visible = [c for c in candles if c.available_at <= datetime.now(timezone.utc)
                   and (cutoff is None or c.open_time < cutoff)]
        page = visible[-limit:]
        return {"dataset_id": row.id, "source_verified": False, "research_eligible": False,
                "historical_execution_enabled": False, "bars": [c.as_dict() for c in page],
                "has_more": len(visible) > len(page), "total_rows": row.quality_report.get("rows", 0),
                "note": "Candle-only replay, no trades or profitability claims. Source remains quarantined."}

    @api.get("/v1/skills/catalog")
    def skill_catalog(_: tuple[CEO, dict] = Depends(current_ceo)):
        return catalog_manifest()

    @api.get("/v1/students/{student_id}/skills")
    def skills_progress(student_id: str, _: tuple[CEO, dict] = Depends(current_ceo),
                        session: Session = Depends(db)):
        student = get_student_or_404(student_id, session)
        try:
            return student_skill_progress(session, student)
        except MemoryError as exc:
            raise HTTPException(status_code=409, detail=f"Memory integrity check failed: {exc}") from exc

    @api.get("/v1/students/{student_id}/memory")
    def student_memory(student_id: str, limit: int = 50, _: tuple[CEO, dict] = Depends(current_ceo),
                       session: Session = Depends(db)):
        get_student_or_404(student_id, session)
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        try:
            return {"student_id": student_id, "episodes": read_student_memory(session, student_id, limit=limit),
                    "qualification": "unqualified", "note": "Research archive only; not independent mastery or profitability evidence."}
        except (MemoryError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=f"Memory integrity check failed: {exc}") from exc

    @api.get("/v1/students/{student_id}/training")
    def training_history(student_id: str, limit: int = 20, _: tuple[CEO, dict] = Depends(current_ceo),
                         session: Session = Depends(db)):
        get_student_or_404(student_id, session)
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        try:
            return {"student_id": student_id, "runs": student_training_runs(session, student_id, limit=limit),
                    "qualification": "unqualified", "automatic_training_enabled": False,
                    "note": "Offline neural research only; development loss is not independent proof."}
        except TrainingError as exc:
            raise HTTPException(status_code=409, detail=f"Training integrity check failed: {exc}") from exc

    @api.get("/v1/students/{student_id}/policy-candidates")
    def policy_candidates(student_id: str, response: Response,
                          _: tuple[CEO, dict] = Depends(current_ceo),
                          session: Session = Depends(db)):
        """Audit-only student policy candidate history; never activates a version."""
        get_student_or_404(student_id, session)
        response.headers["Cache-Control"] = "no-store"
        try:
            return {"student_id": student_id,
                    "candidates": research_policy_history(session, student_id),
                    "qualification": "unqualified",
                    "automatic_policy_activation_enabled": False,
                    "paper_trading_enabled": False, "live_trading_enabled": False,
                    "note": "Five-batch research suggestions only; independent validation and rollback are required."}
        except PolicyResearchError as exc:
            raise HTTPException(status_code=409, detail=f"Policy checkpoint integrity check failed: {exc}") from exc

    @api.get("/v1/students/{student_id}/exams")
    def exam_history(student_id: str, limit: int = 20, _: tuple[CEO, dict] = Depends(current_ceo),
                     session: Session = Depends(db)):
        get_student_or_404(student_id, session)
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        try:
            return {"student_id": student_id, "exams": student_exam_history(session, student_id, limit=limit),
                    "qualification": "unqualified", "automatic_promotion_enabled": False,
                    "note": "Independent offline research comparisons are provisional. Dataset rights and holdout independence are not certified."}
        except ExaminationError as exc:
            raise HTTPException(status_code=409, detail=f"Exam integrity check failed: {exc}") from exc

    @api.post("/v1/research/decision-trace")
    def research_trace(payload: TraceBatchInput, response: Response,
                       user: CEO = Depends(require_csrf),
                       session: Session = Depends(db)):
        """Owner-only bounded read-only analysis, no broker or stored model changes.

        POST transports private user-supplied OHLC values (not a state mutation).
        The inputs remain UNVERIFIED even when a student has a saved learning plan.
        """
        student = get_student_or_404(str(payload.student_id), session)
        plan = max(student.plans, key=lambda p: p.version)
        if plan.mode == "directed" and "XAUUSD" not in plan.markets:
            raise HTTPException(status_code=409, detail="XAUUSD outside student learning plan")
        approved = ({"trend", "range", "breakout"} if plan.mode == "autonomous" else
                    set(plan.skills) & {"trend", "range", "breakout"})
        if not approved:
            raise HTTPException(status_code=409, detail="Student needs an XAUUSD trend/range/breakout research target")
        try:
            model = load_neural_inference(session, student.id, plan_version=plan.version)
            report = inspect_trace_batch(payload, permitted_skills=approved, neural_context=model)
        except ResearchNeuralError as exc:
            raise HTTPException(status_code=409, detail=f"Saved neural model integrity/scope issue: {exc}") from exc
        response.headers["Cache-Control"] = "no-store"
        return report

    @api.post("/v1/students/{student_id}/neural/predict")
    def neural_predict(student_id: str, payload: NeuralPredictionInput,
                       response: Response, user: CEO = Depends(require_csrf),
                       session: Session = Depends(db)):
        """Read-only real checkpoint inference. Does not write to strategy or execute."""
        if str(payload.student_id) != student_id:
            raise HTTPException(status_code=422, detail="Student request identity mismatch")
        student = get_student_or_404(student_id, session)
        plan = max(student.plans, key=lambda p: p.version)
        if plan.mode == "directed" and (
            payload.market not in plan.markets or payload.tactic not in plan.skills):
            raise HTTPException(status_code=409, detail="Neural prediction outside student learning scope")
        try:
            model = load_neural_inference(session, student_id, plan_version=plan.version)
            if not model:
                raise HTTPException(status_code=409, detail="No saved neural weights yet; train student first")
            result = score_neural_candidate(
                model, list(payload.candles), market=payload.market, tactic=payload.tactic)
        except ResearchNeuralError as exc:
            raise HTTPException(status_code=409, detail=f"Neural inference guarded: {exc}") from exc
        response.headers["Cache-Control"] = "no-store"
        return {
            "model": result, "student_id": student_id,
            "research_only": True, "qualified": False,
            "scout_b_empirically_validated": False,
            "guardian": "NOT_EVALUATED", "decision": "NO_TRADE",
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }

    @api.get("/v1/students/{student_id}/candle-study")
    def candle_study(student_id: str, dataset_id: str | None = None,
                     _: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        """Read-only M15 directional study; not neural training or an execution replay.

        Uses only a hash-validated stored dataset. No new records, model weights,
        broker orders or eligibility changes are created by requesting this route.
        """
        student = get_student_or_404(student_id, session)
        plan = max(student.plans, key=lambda p: p.version)
        if plan.mode == "directed" and "XAUUSD" not in plan.markets:
            raise HTTPException(status_code=422, detail="XAUUSD is outside this student's learning plan")
        tactics = tuple(key for key in ("trend", "range", "breakout")
                        if plan.mode == "autonomous" or key in plan.skills)
        if not tactics:
            raise HTTPException(status_code=422, detail="Student needs a trend, range or breakout learning target")
        if dataset_id:
            dataset = session.get(HistoricalDataset, dataset_id)
        else:
            dataset = session.scalar(select(HistoricalDataset)
                                     .order_by(HistoricalDataset.ingested_at.desc(), HistoricalDataset.id.desc()))
        if dataset is None:
            raise HTTPException(status_code=404, detail="No saved XAUUSD dataset. Import an M15 CSV first.")
        if (dataset.state != "quarantined"
            or dataset.source_manifest.get("instrument") != "XAUUSD"
            or dataset.source_manifest.get("timeframe") != "M15"):
            raise HTTPException(status_code=409, detail="Selected dataset is not a quarantined XAUUSD M15 archive")
        try:
            candles = verified_candles(session, dataset, data_root)
            report = study_candles(candles, dataset_id=dataset.id,
                                   source_sha256=dataset.source_hash,
                                   allowed_tactics=tactics)
        except (DataQualityError, CandleStudyError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail=f"Historical research integrity gate: {exc}") from exc
        return {**report, "student_id": student.id, "plan_version": plan.version,
                "quality_warning_count": len(dataset.quality_report.get("warnings", []))}

    @api.get("/v1/students/{student_id}/m15-trade-scenario")
    def m15_trade_scenario(student_id: str, dataset_id: str,
                           _: tuple[CEO, dict] = Depends(current_ceo),
                           session: Session = Depends(db)):
        """Hypothetical *cost scenario* with strict CEO scope; NO order execution.

        Reads only the referenced integrity-checked quarantined XAUUSD M15
        archive. Does not write trade episodes, model weights, paper orders,
        research qualification, audit decisions or approval records.
        """
        student = get_student_or_404(student_id, session)
        plan = max(student.plans, key=lambda p: p.version)
        if plan.mode == "directed" and "XAUUSD" not in plan.markets:
            raise HTTPException(status_code=422, detail="XAUUSD outside student learning plan")
        tactics = tuple(t for t in ("trend", "range", "breakout")
                        if plan.mode == "autonomous" or t in plan.skills)
        if not tactics:
            raise HTTPException(status_code=422, detail="A trend/range/breakout target is required")
        dataset = session.get(HistoricalDataset, dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Unknown imported dataset")
        if (dataset.state != "quarantined" or
            dataset.source_manifest.get("instrument") != "XAUUSD" or
            dataset.source_manifest.get("timeframe") != "M15"):
            raise HTTPException(status_code=409, detail="Requires a quarantined XAUUSD M15 archive")
        try:
            candles = verified_candles(session, dataset, data_root)
            result = study_costed_outcomes(
                candles, dataset_id=dataset.id, source_sha256=dataset.source_hash,
                allowed_tactics=tactics)
        except (DataQualityError, CandleStudyError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail=f"Hypothetical M15 scenario blocked: {exc}") from exc
        return {**result, "student_id": student.id, "plan_version": plan.version,
                "source_description": "Owner-imported, execution price basis unverified"}

    @api.get("/v1/students/{student_id}/academy")
    def academy_status(student_id: str, _: tuple[CEO, dict] = Depends(current_ceo),
                       session: Session = Depends(db)):
        get_student_or_404(student_id, session)
        try:
            return {"curriculum": lesson_plan(session, student_id),
                    "jobs": student_jobs(session, student_id),
                    "autonomous_training_enabled": False,
                    "qualification": "unqualified",
                    "note": "Bounded offline research jobs only. Verified market data is unavailable."}
        except AcademyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.get("/v1/students/{student_id}/evolution")
    def evolution_status(student_id: str, _: tuple[CEO, dict] = Depends(current_ceo),
                         session: Session = Depends(db)):
        try:
            return {"tree": student_evolution(session, student_id),
                    "lessons": peer_lessons(session, student_id),
                    "mentor_status": mentorship_eligibility(session, student_id, 'tactic:trend'),
                    "qualification": "unqualified", "automatic_promotion": False}
        except EvolutionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.get("/v1/sentinel/report")
    def sentinel_report(_: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        try:
            return scan_health(session, data_root=data_root, checkpoints_root=data_root/'weights',
                               now=datetime.now(timezone.utc))
        except (SentinelError, OSError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=f"Sentinel scan failed: {exc}") from exc

    @api.post("/v1/safety/emergency-stop")
    def emergency_stop(user: CEO = Depends(require_csrf), session: Session = Depends(db)):
        result=engage_stop(session,user.id,'CEO manually engaged emergency safety stop')
        session.add(AuditEvent(actor_id=user.id,action='safety.emergency_stop',subject_id='global',
                               detail={'locked':True}))
        session.commit()
        return result

    @api.get("/v1/students/{student_id}/paper/btc/diagnostics")
    def btc_paper_diagnostics(student_id: str, _: tuple[CEO, dict] = Depends(current_ceo),
                              session: Session = Depends(db)):
        """GET-only; associates a directed BTC student with a verified paper account."""
        student = get_student_or_404(student_id, session)
        latest_plan = student.plans[-1] if student.plans else None
        if latest_plan is None or "BTCUSD" not in latest_plan.markets:
            raise HTTPException(status_code=409, detail="Student requires a BTCUSD learning plan")
        key_id = os.environ.get("ALPACA_PAPER_API_KEY_ID", "")
        secret = os.environ.get("ALPACA_PAPER_API_SECRET_KEY", "")
        expected = os.environ.get("ALPACA_PAPER_EXPECTED_ACCOUNT_ID", "")
        if not (key_id and secret and expected):
            return {
                "student_id": student_id,
                "instrument": "BTCUSD",
                "configured": False,
                "account_verified": False,
                "broker_connected": False,
                "paper_trading_enabled": False,
                "live_trading_enabled": False,
                "reason": "paper_credentials_not_configured",
            }
        try:
            snapshot = preview_btc_paper(
                key_id=key_id, secret_key=secret, expected_account_id=expected
            )
        except PaperPreviewError:
            raise HTTPException(status_code=503, detail="BTC paper read-only verification failed") from None
        return {
            "student_id": student_id,
            "instrument": "BTCUSD",
            "configured": True,
            "broker_connected": False,
            **snapshot,
        }

    @api.get("/v1/paper/account")
    def paper_account(response: Response, _: tuple[CEO, dict] = Depends(current_ceo)):
        """CEO-only GET snapshot. GitHub Actions secrets are NOT backend runtime secrets."""
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        # Never combine credentials from different env-var naming conventions.
        key_id = os.environ.get("APCA_API_KEY_ID", "")
        secret = os.environ.get("APCA_API_SECRET_KEY", "")
        if not key_id and not secret:
            key_id = os.environ.get("ALPACA_PAPER_API_KEY_ID", "")
            secret = os.environ.get("ALPACA_PAPER_API_SECRET_KEY", "")
        if not key_id or not secret:
            return {
                "configured": False,
                "paper_api_readable": False,
                "reason": "runtime_credentials_not_configured",
                "paper_trading_enabled": False,
                "live_trading_enabled": False,
                "note": "Set paper credentials in the secured backend runtime; Actions secrets alone are insufficient.",
            }
        try:
            return read_paper_account(
                key_id=key_id, secret_key=secret,
                expected_account_id=os.environ.get("ALPACA_PAPER_EXPECTED_ACCOUNT_ID", ""),
            )
        except PaperAccountReadError:
            raise HTTPException(
                status_code=503,
                detail="Alpaca paper snapshot unavailable; verify runtime secrets and paper account binding.",
                headers={"Cache-Control": "no-store"},
            ) from None

    @api.get("/v1/paper/readiness")
    def paper_readiness(_: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        return evaluate_readiness(session)

    @api.get("/v1/paper/review-requests")
    def paper_review_history(_: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        try:
            return {"requests": paper_requests(session), "paper_trading_enabled": False,
                    "note": "Review records do not authorise a pilot."}
        except PaperReadinessError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.get("/v1/students", response_model=list[StudentResponse])
    def students(_: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        rows = session.scalars(select(Student).options(selectinload(Student.plans)).order_by(Student.created_at.asc(), Student.id.asc())).all()
        return [output(row) for row in rows]

    @api.post("/v1/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
    def add_student(payload: CreateStudent, user: CEO = Depends(require_csrf), session: Session = Depends(db)):
        student = Student(name=payload.name, name_key=name_key(payload.name))
        plan = LearningPlan(student=student, version=1, mode=payload.mode.value,
                            markets=[m.value for m in payload.markets], skills=[s.value for s in payload.skills],
                            reason="Initial CEO-approved research plan")
        session.add_all([student, plan])
        try:
            session.flush()
            session.add(AuditEvent(actor_id=user.id, action="student.created", subject_id=student.id,
                                   detail={"name": student.name, "mode": plan.mode, "plan_version": 1}))
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Student name already in use") from exc
        return output(get_student_or_404(student.id, session))

    @api.get("/v1/students/{student_id}", response_model=StudentResponse)
    def student_detail(student_id: str, _: tuple[CEO, dict] = Depends(current_ceo), session: Session = Depends(db)):
        return output(get_student_or_404(student_id, session), full=True)

    @api.patch("/v1/students/{student_id}/direction", response_model=StudentResponse)
    def change_direction(student_id: str, payload: ChangeDirection, user: CEO = Depends(require_csrf), session: Session = Depends(db)):
        student = get_student_or_404(student_id, session)
        last = max(plan.version for plan in student.plans)
        plan = LearningPlan(student_id=student.id, version=last + 1, mode=payload.mode.value,
                            markets=[m.value for m in payload.markets], skills=[s.value for s in payload.skills],
                            reason=payload.reason.strip())
        student.plans.append(plan)
        student.updated_at = datetime.now(timezone.utc)
        session.add(AuditEvent(actor_id=user.id, action="student.direction_changed", subject_id=student.id,
                               detail={"from_version": last, "to_version": last + 1, "mode": plan.mode}))
        session.commit()
        session.refresh(student)
        # Re-read relationship after commit so version order remains deterministic.
        return output(get_student_or_404(student_id, session), full=True)

    @api.patch("/v1/students/{student_id}/name", response_model=StudentResponse)
    def rename_student(student_id: str, payload: RenameStudent, user: CEO = Depends(require_csrf), session: Session = Depends(db)):
        student = get_student_or_404(student_id, session)
        previous = student.name
        student.name, student.name_key = payload.name, name_key(payload.name)
        student.updated_at = datetime.now(timezone.utc)
        session.add(AuditEvent(actor_id=user.id, action="student.renamed", subject_id=student.id,
                               detail={"previous": previous, "updated": student.name}))
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Student name already in use") from exc
        return output(get_student_or_404(student_id, session), full=True)

    # Optional single-origin mobile preview; default local/test API remains unchanged.
    from agentic_trading.preview_web import install_preview_routes
    install_preview_routes(api, cfg, session_factory, limiter)
    return api


app = create_app()
