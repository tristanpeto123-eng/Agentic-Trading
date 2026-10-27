"""Sprint 1 CEO app. No broker, order execution or model-training routes exist."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
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
from agentic_trading.evolution import student_evolution, peer_lessons, mentorship_eligibility, EvolutionError
from agentic_trading.sentinel import scan_health, engage_stop, safety_latch, SentinelError
from agentic_trading.paper_readiness import evaluate_readiness, paper_requests, PaperReadinessError
from agentic_trading.providers.alpaca_paper_readonly import preview_btc_paper, PaperPreviewError
from agentic_trading.settings import Settings
from agentic_trading.historical_store import DATABASE_ARTIFACT_PATH, store_historical_artifacts, verified_candles
from agentic_trading.historical_demo import build_historical_demo
from agentic_trading.storage import AuditEvent, Base, CEO, LearningPlan, Student, HistoricalDataset, new_session_factory


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

    @api.get("/v1/capabilities")
    def capabilities():
        return {
            "name": "Agentic Trading", "stage": "sprint_11_paper_readiness",
            "research_training_enabled": False, "historical_execution_enabled": False,
            "paper_trading_enabled": False, "live_trading_enabled": False,
            "broker_connected": False, "student_creation_enabled": True,
            "historical_data_import_enabled": historical_upload_available, "historical_research_enabled": True, "historical_candle_replay_enabled": True, "historical_synthetic_demo_enabled": True, "research_data_qualified": False,
            "skills_catalog_enabled": True, "episodic_memory_read_enabled": True,
            "independent_skill_mastery_enabled": False, "automatic_memory_ingest_enabled": False,
            "offline_neural_research_training_available": True, "automatic_training_enabled": False,
            "independent_examiner_enabled": False,
            "offline_research_examiner_available": True, "academy_scheduler_available": True, "strategy_dna_read_enabled": True, "peer_research_lessons_enabled": True, "sentinel_read_enabled": True, "emergency_stop_enabled": True, "paper_readiness_report_enabled": True, "independent_examination_qualification_enabled": False,
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
