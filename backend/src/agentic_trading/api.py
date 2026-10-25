"""Sprint 1 CEO app. No broker, order execution or model-training routes exist."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import time

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from agentic_trading import __version__
from agentic_trading.auth import (
    SESSION_COOKIE, SESSION_SECONDS, csrf_token, csrf_valid, make_session, read_session, verify_password
)
from agentic_trading.schemas import (
    ChangeDirection, CreateStudent, LearningMode, LoginRequest, RenameStudent,
    StudentResponse, name_key,
)
from agentic_trading.settings import Settings
from agentic_trading.storage import AuditEvent, Base, CEO, LearningPlan, Student, new_session_factory


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
        return {"status": "ok", "component": "api", "sprint": "S1"}

    @api.get("/v1/capabilities")
    def capabilities():
        return {
            "name": "Agentic Trading", "stage": "sprint_1_app_foundation",
            "research_training_enabled": False, "historical_execution_enabled": False,
            "paper_trading_enabled": False, "live_trading_enabled": False,
            "broker_connected": False, "student_creation_enabled": True,
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
        return {
            "students_total": total, "students_training": 0, "research_qualified": 0,
            "research_status": "not_started", "market_data_status": "not_connected",
            "historical_trading": "disabled", "paper_trading": "disabled",
            "live_trading": "disabled", "system_health": "api_online",
            "net_pnl": None, "open_positions": None,
            "attention": ["Verified historical market data not yet configured (Sprint 2)"],
        }

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

    return api


app = create_app()
