from fastapi.testclient import TestClient
from agentic_trading.api import app

def test_health_and_capabilities():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    caps = c.get("/v1/capabilities")
    assert caps.status_code == 200
    assert caps.json()["live_trading_enabled"] is False
    assert caps.json()["paper_trading_enabled"] is False
    assert caps.json()["student_creation_enabled"] is False

def test_no_trading_or_student_creation_endpoints():
    c = TestClient(app)
    for route in ("/v1/orders", "/v1/students", "/v1/broker/connect", "/v1/approve"):
        assert c.post(route, json={}).status_code == 404
