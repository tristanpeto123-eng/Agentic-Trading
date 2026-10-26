"""Startup configuration, with fail-closed production authentication settings."""
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    environment: str = "development"
    data_dir: str = ""
    allowed_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    def __post_init__(self):
        if self.environment != "development" and len(self.secret_key) < 32:
            raise RuntimeError("SESSION_SECRET must be at least 32 characters outside development")
        if self.environment != "development" and not self.allowed_origins:
            raise RuntimeError("ALLOWED_ORIGINS required outside development")

    @property
    def cookie_secure(self) -> bool:
        return self.environment == "production"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("APP_ENV", "development")
        secret = os.getenv("SESSION_SECRET", "")
        if env != "development" and len(secret) < 32:
            raise RuntimeError("SESSION_SECRET must be at least 32 characters outside development")
        if not secret:
            # Local testing only; a restart invalidates local sessions.
            secret = os.urandom(32).hex()
        database = os.getenv("DATABASE_URL") or f"sqlite:///{Path.cwd() / 'agentic_local.sqlite3'}"
        origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        return cls(database, secret, env, os.getenv("DATA_STORAGE_DIR", ""), tuple(s.strip().rstrip("/") for s in origins.split(",") if s.strip()))
