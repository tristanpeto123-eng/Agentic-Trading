"""Research-preview tests: secure one-time setup and SPA isolation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentic_trading.api import create_app
from agentic_trading.settings import Settings
from agentic_trading.storage import Base, new_session_factory


ORIGIN = "https://agentic-preview.up.railway.app"
TOKEN = "test-only-placeholder-setup-code-" + "s" * 48


def _client(tmp_path, monkeypatch):
    dist = tmp_path / "frontend" / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Agentic Preview</title>", encoding="utf-8")
    (assets / "demo.js").write_text("console.log('research preview')", encoding="utf-8")
    monkeypatch.setenv("WEB_DIST_DIR", str(dist))
    monkeypatch.setenv("PREVIEW_SETUP_TOKEN", TOKEN)
    database_url = "sqlite:///" + str(tmp_path / "preview.sqlite3")
    engine, _ = new_session_factory(database_url)
    Base.metadata.create_all(engine)
    cfg = Settings(database_url, "y" * 48, "production", "", (ORIGIN,))
    return TestClient(create_app(cfg), base_url=ORIGIN, follow_redirects=False)


def test_preview_one_time_setup_and_same_origin(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    page = client.get("/setup")
    assert page.status_code == 200
    assert "CEO login" in page.text
    assert "no-store" in page.headers["cache-control"]
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    payload = {"email": "OWNER@example.com", "password": "strong unique example passphrase",
               "setup_token": TOKEN}
    assert client.post("/v1/auth/setup", json=payload).status_code == 403  # No Origin.
    assert client.post("/v1/auth/setup", json=payload,
                       headers={"origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/v1/auth/setup", json={**payload, "setup_token": "wrong"},
                       headers={"origin": ORIGIN}).status_code == 403
    created = client.post("/v1/auth/setup", json=payload, headers={"origin": ORIGIN})
    assert created.status_code == 201, created.text
    assert created.json()["created"] is True
    assert client.get("/setup").status_code == 303
    assert client.post("/v1/auth/setup", json=payload, headers={"origin": ORIGIN}).status_code == 409

    # Unauthenticated student data remains protected, even though login HTML is public.
    assert client.get("/v1/students").status_code == 401
    assert client.get("/").status_code == 200
    assert "Agentic Preview" in client.get("/deep/link").text
    assert client.get("/assets/demo.js").status_code == 200
    assert client.get("/v1/nonexistent").status_code == 404
    assert client.get("/bad.js").status_code == 404


def test_missing_setup_token_fails_closed(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("PREVIEW_SETUP_TOKEN", "")
    # Configuration is read on startup; replacing it requires another app instance.
    cfg = Settings("sqlite:///" + str(tmp_path / "preview.sqlite3"),
                   "y" * 48, "production", "", (ORIGIN,))
    empty = TestClient(create_app(cfg), base_url=ORIGIN, follow_redirects=False)
    assert empty.get("/setup").status_code == 503
    assert empty.post("/v1/auth/setup", json={
        "email": "owner@example.com", "password": "long secure password", "setup_token": TOKEN,
    }, headers={"origin": ORIGIN}).status_code == 404


def test_preview_requires_production_when_enabled(tmp_path, monkeypatch):
    _client(tmp_path, monkeypatch)
    cfg = Settings("sqlite:///" + str(tmp_path / "preview.sqlite3"),
                   "z" * 48, "development", "", (ORIGIN,))
    with pytest.raises(RuntimeError, match="APP_ENV=production"):
        create_app(cfg)
