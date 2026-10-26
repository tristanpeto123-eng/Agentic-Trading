"""Render free-preview contracts: data URI normalization and safe opt-in."""
from agentic_trading.database_url import normalize_database_url
from agentic_trading.settings import Settings


def test_postgres_uri_uses_psycopg3():
    assert normalize_database_url("postgres://user:pass@internal:5432/trades") == (
        "postgresql+psycopg://user:pass@internal:5432/trades")
    assert normalize_database_url("postgresql://u:p@h/d?sslmode=require") == (
        "postgresql+psycopg://u:p@h/d?sslmode=require")
    assert normalize_database_url("postgresql+psycopg://user:pass@h/d") == (
        "postgresql+psycopg://user:pass@h/d")
    assert normalize_database_url("sqlite:////tmp/test.db") == "sqlite:////tmp/test.db"


def test_render_env_is_fail_closed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@internal/database")
    monkeypatch.setenv("SESSION_SECRET", "s" * 50)
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.onrender.com")
    cfg = Settings.from_env()
    assert cfg.database_url == "postgresql+psycopg://user:pass@internal/database"
    assert cfg.cookie_secure
    assert cfg.allowed_origins == ("https://example.onrender.com",)
