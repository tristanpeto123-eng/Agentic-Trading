"""Auth, CEO-only writes, DB persistence, plan immutability, and fail-closed controls."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentic_trading.api import create_app
from agentic_trading.auth import password_hash
from agentic_trading.settings import Settings
from agentic_trading.storage import Base, CEO, AuditEvent, Student, LearningPlan, new_session_factory


@pytest.fixture
def setup(tmp_path: Path):
    cfg = Settings(database_url=f"sqlite:///{tmp_path / 'app.sqlite3'}", secret_key="A" * 48)
    engine, factory = new_session_factory(cfg.database_url)
    Base.metadata.create_all(engine)
    with factory() as session:
        session.add(CEO(email="owner@example.org", password_hash=password_hash("long-local-test-password")))
        session.commit()
    engine.dispose()
    return cfg


def logged_in(cfg):
    c = TestClient(create_app(cfg))
    login = c.post("/v1/auth/login", json={"email": "owner@example.org", "password": "long-local-test-password"})
    assert login.status_code == 200, login.text
    return c, {"X-CSRF-Token": login.json()["csrf_token"]}


def test_unauthenticated_read_and_write_blocked(setup):
    c = TestClient(create_app(setup))
    assert c.get("/v1/dashboard").status_code == 401
    assert c.get("/v1/students").status_code == 401
    assert c.post("/v1/students", json={"name": "Orion"}).status_code == 401
    assert c.post("/v1/auth/login", json={"email": "owner@example.org", "password": "wrong"}).status_code == 401


def test_create_student_duplicate_and_restart_persistence(setup):
    c, headers = logged_in(setup)
    assert c.post("/v1/students", json={"name": "Orion"}).status_code == 403
    invalid_csrf = c.post("/v1/students", headers={"X-CSRF-Token": "fake"}, json={"name": "Orion"})
    assert invalid_csrf.status_code == 403
    created = c.post("/v1/students", headers=headers, json={"name": "Orion"})
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["name"] == "Orion"
    assert item["learning_plan"]["version"] == 1
    assert item["learning_plan"]["mode"] == "autonomous"
    assert item["training_active"] is False
    assert item["qualification"] == "unqualified"
    assert c.post("/v1/students", headers=headers, json={"name": " oRIoN "}).status_code == 409
    # Restart app with the exact same persisted DB, then fetch the named student.
    fresh = TestClient(create_app(setup))
    login = fresh.post("/v1/auth/login", json={"email": "owner@example.org", "password": "long-local-test-password"})
    assert login.status_code == 200
    rows = fresh.get("/v1/students").json()
    assert len(rows) == 1 and rows[0]["id"] == item["id"]
    assert fresh.get("/v1/dashboard").json()["students_total"] == 1


def test_directed_plan_versions_retain_history_and_identity(setup):
    c, headers = logged_in(setup)
    created = c.post("/v1/students", headers=headers, json={
        "name": "Nova", "mode": "directed", "markets": ["XAUUSD"], "skills": ["trend", "breakout"]
    })
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    changed = c.patch(f"/v1/students/{sid}/direction", headers=headers, json={
        "mode": "autonomous", "reason": "Let Academy choose the next skill"
    })
    assert changed.status_code == 200, changed.text
    student = changed.json()
    assert student["id"] == sid
    assert student["learning_plan"]["version"] == 2
    assert student["learning_plan"]["mode"] == "autonomous"
    assert [p["version"] for p in student["plan_history"]] == [1, 2]
    assert student["plan_history"][0]["markets"] == ["XAUUSD"]
    assert student["plan_history"][0]["skills"] == ["trend", "breakout"]
    assert c.get(f"/v1/students/{sid}").json()["plan_history"][0]["mode"] == "directed"
    assert c.get("/v1/capabilities").json()["live_trading_enabled"] is False


def test_rename_identity_and_normalized_unique_name(setup):
    c, h = logged_in(setup)
    orion = c.post("/v1/students", headers=h, json={"name": "Orion"}).json()
    nova = c.post("/v1/students", headers=h, json={"name": "Nova"}).json()
    assert c.patch(f"/v1/students/{nova['id']}/name", headers=h, json={"name": "ORION"}).status_code == 409
    r = c.patch(f"/v1/students/{orion['id']}/name", headers=h, json={"name": "Orion Prime"})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == orion["id"]
    assert r.json()["learning_plan"]["version"] == 1
    assert c.get("/v1/students").json()[0]["name"] == "Orion Prime"


def test_invalid_scopes_rejected(setup):
    c, h = logged_in(setup)
    cases = [
        {"name": "Nova", "mode": "directed", "markets": ["XAUUSD"], "skills": []},
        {"name": "Nova", "mode": "autonomous", "markets": ["XAUUSD"]},
        {"name": "Nova", "mode": "directed", "markets": ["XAUUSD", "XAUUSD"], "skills": ["trend"]},
        {"name": "@bad!"},
        {"name": "Nova", "mode": "directed", "markets": ["not_a_market"], "skills": ["trend"]},
    ]
    for case in cases:
        r = c.post("/v1/students", headers=h, json=case)
        assert r.status_code == 422, (case, r.text)
    assert c.get("/v1/dashboard").json()["students_total"] == 0


def test_cross_origin_and_logout(setup):
    c, h = logged_in(setup)
    r = c.post("/v1/students", headers={**h, "Origin": "https://attacker.example"}, json={"name": "Nova"})
    assert r.status_code == 403
    me = c.get("/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "ceo"
    assert c.post("/v1/auth/logout", headers=h).status_code == 200
    assert c.get("/v1/students").status_code == 401


def test_audit_events_recorded(setup):
    c, h = logged_in(setup)
    sid = c.post("/v1/students", headers=h, json={"name": "Orion"}).json()["id"]
    c.patch(f"/v1/students/{sid}/direction", headers=h, json={"mode": "directed", "markets": ["XAUUSD"], "skills": ["trend"]})
    c.patch(f"/v1/students/{sid}/name", headers=h, json={"name": "Orion Gold"})
    _, factory = new_session_factory(setup.database_url)
    with factory() as session:
        events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
        assert {e.action for e in events} == {"student.created", "student.direction_changed", "student.renamed"}


def test_password_and_production_configuration_fail_closed():
    with pytest.raises(ValueError):
        password_hash("short")
    with pytest.raises(RuntimeError):
        Settings(database_url="sqlite://", secret_key="tiny", environment="production")
