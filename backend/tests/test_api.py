"""Sprint 1: public capabilities are honest; no execution routes exist."""
from fastapi.testclient import TestClient
from agentic_trading.api import app


def test_health_and_capabilities():
    c = TestClient(app)
    assert c.get("/health").json()["sprint"] == "S10"
    caps = c.get("/v1/capabilities").json()
    assert caps["live_trading_enabled"] is False
    assert caps["paper_trading_enabled"] is False
    assert caps["research_training_enabled"] is False
    assert caps["student_creation_enabled"] is True


def test_no_order_or_broker_endpoints():
    c = TestClient(app)
    for route in ("/v1/orders", "/v1/broker/connect", "/v1/approve"):
        assert c.post(route, json={}).status_code == 404
    assert c.get("/v1/students").status_code == 401
