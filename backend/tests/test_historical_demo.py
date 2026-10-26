"""Synthetic historical simulation is a view, never student qualification or live trading."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from agentic_trading.historical_demo import build_historical_demo, FIXTURE_LABEL
from agentic_trading.api import create_app
from agentic_trading.settings import Settings
from agentic_trading.storage import Base, new_session_factory


def test_deterministic_demo_trades_from_actual_replay_engine():
    first = build_historical_demo()
    second = build_historical_demo()
    assert first == second
    assert first["fixture"] == FIXTURE_LABEL
    assert first["synthetic"] is True
    assert first["student_model_generated"] is False
    assert first["qualification_eligible"] is False
    assert not first["paper_trading_enabled"]
    assert not first["live_trading_enabled"]
    assert len(first["prices"]) == len(first["equity"]) == 180
    trades = first["trades"]
    assert len(trades) == 5
    metrics = first["metrics"]
    closed = [t for t in trades if t["status"] == "CLOSED"]
    assert len(closed) == metrics["closed"]
    assert metrics["wins"] + metrics["losses"] <= metrics["closed"]
    assert Decimal(metrics["net_pnl_usd"]) == sum(
        (Decimal(t["net_pnl_usd"]) for t in closed), Decimal("0"))
    assert Decimal(metrics["ending_equity_usd"]) == (
        Decimal(metrics["starting_equity_usd"]) + Decimal(metrics["net_pnl_usd"]))
    assert metrics["journal_sha256"] == second["metrics"]["journal_sha256"]


def test_demo_requires_ceo_and_keeps_trading_disabled(tmp_path):
    url = "sqlite:///" + str(tmp_path / "demo.sqlite3")
    engine, _ = new_session_factory(url)
    Base.metadata.create_all(engine)
    with TestClient(create_app(Settings(url, "s" * 48))) as client:
        assert client.get("/v1/historical/demo").status_code == 401
        capabilities = client.get("/v1/capabilities").json()
        assert capabilities["historical_synthetic_demo_enabled"] is True
        assert capabilities["historical_execution_enabled"] is False
        assert capabilities["paper_trading_enabled"] is False
        assert capabilities["live_trading_enabled"] is False
        assert client.post("/v1/historical/orders").status_code == 404
        assert client.post("/v1/paper/orders").status_code == 404
