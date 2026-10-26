"""Durable CEO, student, training-plan and audit records (SQLite dev / PostgreSQL ready)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CEO(Base):
    __tablename__ = "ceo_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="ceo", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    name_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="research_pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    plans: Mapped[list[LearningPlan]] = relationship(back_populates="student", cascade="all, delete-orphan", order_by="LearningPlan.version")


class LearningPlan(Base):
    __tablename__ = "learning_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    markets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    student: Mapped[Student] = relationship(back_populates="plans")
    __table_args__ = (Index("ix_student_plan_version", "student_id", "version", unique=True),)


class HistoricalDataset(Base):
    __tablename__ = "historical_datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    canonical_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    quality_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_path: Mapped[str] = mapped_column(String(300), nullable=False)
    canonical_path: Mapped[str] = mapped_column(String(300), nullable=False)
    state: Mapped[str] = mapped_column(String(40), default="quarantined", nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TradeExperience(Base):
    """Immutable by application contract; database access restricted to trusted workers."""
    __tablename__ = "trade_experiences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    partition: Mapped[str] = mapped_column(String(20), nullable=False)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    skill_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    net_pnl_usd: Mapped[str] = mapped_column(String(64), nullable=False)
    net_r: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        Index("ix_experience_student_asof", "student_id", "available_at"),
        Index("ix_experience_student_partition", "student_id", "partition"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_id: Mapped[str] = mapped_column(String(36), ForeignKey("ceo_users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def new_session_factory(database_url: str):
    engine = create_engine(database_url, pool_pre_ping=True, connect_args={"check_same_thread": False} if database_url.startswith("sqlite:") else {})
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


class TrainingRun(Base):
    """Frozen student research job: NO exam, promotion or trading authority."""
    __tablename__ = "training_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False)
    config_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="research_only")
    qualification: Mapped[str] = mapped_column(String(30), nullable=False, default="unqualified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_training_student_created", "student_id", "created_at"),)


class TrainingCheckpoint(Base):
    """One immutable, checksum-verified, pickle-free weights artifact per epoch."""
    __tablename__ = "training_checkpoints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("training_runs.id"), nullable=False)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    relative_path: Mapped[str] = mapped_column(String(300), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    train_loss: Mapped[float] = mapped_column(Float, nullable=False)
    development_loss: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_training_run_epoch", "run_id", "epoch", unique=True),)


class ExamRun(Base):
    """Immutable-by-service experimental exam results; never deployment credentials."""
    __tablename__ = "exam_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False)
    training_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("training_runs.id"), nullable=False)
    plan_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    report_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    report: Mapped[dict] = mapped_column(JSON, nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("historical_datasets.id"), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    challenger_model_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    tactic: Mapped[str] = mapped_column(String(32), nullable=False)
    verdict: Mapped[str] = mapped_column(String(36), nullable=False)
    qualification: Mapped[str] = mapped_column(String(30), nullable=False, default="unqualified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_exams_student_created", "student_id", "created_at"),)


class AcademyJob(Base):
    """Durable versioned research-only job; no authority to promote/deploy."""
    __tablename__ = 'academy_jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey('students.id'), nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    spec: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(36), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index('ix_academy_student_state', 'student_id', 'state'),)


class StrategyRevision(Base):
    """Versioned strategy genealogy; no research/live promotion state."""
    __tablename__ = 'strategy_revisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey('students.id'), nullable=False)
    family: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    tactic: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__=(Index('ix_strategy_family_version','student_id','family','version',unique=True),)


class PeerLesson(Base):
    """Research-only interstudent teaching reference, no credential transfer."""
    __tablename__='peer_lessons'
    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    source_student_id: Mapped[str] = mapped_column(String(36),ForeignKey('students.id'),nullable=False)
    target_student_id: Mapped[str] = mapped_column(String(36),ForeignKey('students.id'),nullable=False)
    payload: Mapped[dict] = mapped_column(JSON,nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64),unique=True,nullable=False)
    __table_args__=(Index('ix_peer_target','target_student_id'),)


class SafetyLatch(Base):
    """Global deny latch; no API unlock available until future CEO approval gate."""
    __tablename__='safety_latches'
    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    reason: Mapped[str] = mapped_column(String(200),nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36),ForeignKey('ceo_users.id'),nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
