"""Public deployment revision is safe and never claims a missing SHA is current."""
from fastapi.testclient import TestClient
from agentic_trading.api import app


def test_render_health_reports_exact_40_hex_commit(monkeypatch):
    expected = "9fb51fbc733535b32a16be0d471f0d287023b70f"
    monkeypatch.setenv("RENDER_GIT_COMMIT", expected)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["deployed_commit"] == expected


def test_render_health_does_not_invent_revision(monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["deployed_commit"] is None


def test_render_health_rejects_invalid_revision(monkeypatch):
    for invalid in ("", "local", "../secrets", "abc", "g" * 40, "0" * 39):
        monkeypatch.setenv("RENDER_GIT_COMMIT", invalid)
        assert TestClient(app).get("/health").json()["deployed_commit"] is None
