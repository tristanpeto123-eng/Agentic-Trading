"""Initial Alembic migration must initialise a new durable database."""
from pathlib import Path
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from agentic_trading.settings import Settings
from agentic_trading.storage import new_session_factory


def test_initial_schema_migration(tmp_path: Path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'new_db.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    engine, _ = new_session_factory(url)
    tables = set(inspect(engine).get_table_names())
    assert {"ceo_users", "students", "learning_plans", "audit_events", "historical_datasets", "trade_experiences", "training_runs", "training_checkpoints", "alembic_version"} <= tables
    indexes = {x["name"] for x in inspect(engine).get_indexes("learning_plans")}
    assert "ix_student_plan_version" in indexes
    experience_indexes = {x["name"] for x in inspect(engine).get_indexes("trade_experiences")}
    assert {"ix_experience_student_asof", "ix_experience_student_partition"} <= experience_indexes
    command.upgrade(cfg, "head")  # repeat-safe
    engine.dispose()
