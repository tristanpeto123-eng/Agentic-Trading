"""Temporary CI-only CEO bootstrap. Never use for production accounts."""
import os
from sqlalchemy import select
from agentic_trading.auth import password_hash
from agentic_trading.settings import Settings
from agentic_trading.storage import CEO, new_session_factory

secret = os.environ["CEO_TEST_PASSWORD"]
engine, sessions = new_session_factory(Settings.from_env().database_url)
with sessions() as session:
    if session.scalar(select(CEO).where(CEO.email == "ci@example.invalid")) is not None:
        raise RuntimeError("CI test user already exists")
    session.add(CEO(email="ci@example.invalid", password_hash=password_hash(secret)))
    session.commit()
engine.dispose()
