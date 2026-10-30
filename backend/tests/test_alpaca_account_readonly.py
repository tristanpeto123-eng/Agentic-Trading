"""Sprint 12: CEO-only Alpaca paper snapshot, strict GET-only transport and no orders."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from agentic_trading.api import create_app
from agentic_trading.auth import password_hash
from agentic_trading.providers.alpaca_account_readonly import (
    PaperAccountReadError, read_paper_account,
)
from agentic_trading.settings import Settings
from agentic_trading.storage import Base, CEO, new_session_factory


ACCOUNT = "d88b87e1-79d2-4ed9-8675-73b3520b3356"


def paper_client(*, account_id=ACCOUNT, account_status="ACTIVE", fail=False, calls=None):
    def response(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        assert request.method == "GET"
        assert request.url.host == "paper-api.alpaca.markets"
        assert request.headers.get("APCA-API-KEY-ID") == "paper-key-123"
        assert request.headers.get("APCA-API-SECRET-KEY") == "secret-for-tests"
        if fail:
            return httpx.Response(401, json={"message": "unauthorized example private"})
        if request.url.path == "/v2/account":
            return httpx.Response(200, json={
                "id": account_id, "status": account_status, "currency": "USD",
                "cash": "175.12", "equity": "198.41", "buying_power": "200.10",
                "account_number": "CONFIDENTIAL_NUMBER",
            })
        if request.url.path == "/v2/positions":
            return httpx.Response(200, json=[
                {"symbol": "BTCUSD", "side": "long", "qty": "0.001",
                 "market_value": "25.00", "unrealized_pl": "0.41",
                 "avg_entry_price": "24000", "current_price": "25000",
                 "asset_id": "CONFIDENTIAL_ASSET_ID"},
            ])
        if request.url.path == "/v2/orders":
            assert request.url.params.get("status") == "open"
            return httpx.Response(200, json=[{"id": "CONFIDENTIAL_ORDER_ID"}])
        raise AssertionError("Unexpected route")
    return httpx.Client(transport=httpx.MockTransport(response))


def test_read_only_snapshot_and_sanitization():
    calls = []
    with paper_client(calls=calls) as client:
        result = read_paper_account(
            key_id="paper-key-123", secret_key="secret-for-tests",
            expected_account_id=ACCOUNT, client=client,
        )
    assert calls == ["/v2/account", "/v2/positions", "/v2/orders"]
    assert result["paper_api_readable"] is True
    assert result["account_bound"] is True
    assert result["cash"] == "175.12"
    assert result["equity"] == "198.41"
    assert result["open_orders_count"] == 1
    assert result["positions"][0]["symbol"] == "BTCUSD"
    assert result["paper_trading_enabled"] is False
    assert result["student_order_execution_enabled"] is False
    assert result["live_trading_enabled"] is False
    serialized = str(result)
    for forbidden in ["paper-key-123", "secret-for-tests", ACCOUNT, "CONFIDENTIAL_NUMBER",
                      "CONFIDENTIAL_ORDER_ID", "CONFIDENTIAL_ASSET_ID"]:
        assert forbidden not in serialized


def test_account_binding_mismatch_prevents_position_queries():
    calls = []
    with paper_client(account_id="another-paper-account", calls=calls) as client:
        with pytest.raises(PaperAccountReadError, match="does not match"):
            read_paper_account(key_id="paper-key-123", secret_key="secret-for-tests",
                               expected_account_id=ACCOUNT, client=client)
    assert calls == ["/v2/account"]


def test_unauthorised_response_is_sanitized():
    with paper_client(fail=True) as client:
        with pytest.raises(PaperAccountReadError) as exc:
            read_paper_account(key_id="paper-key-123", secret_key="secret-for-tests", client=client)
    assert "private" not in str(exc.value)
    assert "paper-key-123" not in str(exc.value)


def test_missing_credentials_no_network():
    with pytest.raises(PaperAccountReadError, match="required"):
        read_paper_account(key_id="", secret_key="")


def test_ceo_only_route_and_runtime_secrets(monkeypatch, tmp_path):
    for key in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY",
                "ALPACA_PAPER_API_KEY_ID", "ALPACA_PAPER_API_SECRET_KEY",
                "ALPACA_PAPER_EXPECTED_ACCOUNT_ID"):
        monkeypatch.delenv(key, raising=False)
    cfg = Settings(database_url=f"sqlite:///{tmp_path / 's12.db'}",
                   secret_key="D" * 48)
    engine, factory = new_session_factory(cfg.database_url)
    Base.metadata.create_all(engine)
    with factory() as session:
        session.add(CEO(email="ceo@example.test", password_hash=password_hash("long-test-password")))
        session.commit()
    engine.dispose()
    app = TestClient(create_app(cfg))
    assert app.get("/v1/paper/account").status_code == 401
    login = app.post("/v1/auth/login", json={
        "email": "ceo@example.test", "password": "long-test-password"
    })
    assert login.status_code == 200
    not_configured = app.get("/v1/paper/account")
    assert not_configured.status_code == 200
    assert not_configured.headers["cache-control"] == "no-store"
    assert not_configured.json()["configured"] is False
    assert not_configured.json()["paper_trading_enabled"] is False

    def read_mock(**kwargs):
        assert kwargs["key_id"] == "paper-key-123"
        assert kwargs["secret_key"] == "secret-for-tests"
        assert kwargs["expected_account_id"] == ACCOUNT
        return {"configured": True, "paper_api_readable": True,
                "account_status": "ACTIVE", "paper_trading_enabled": False,
                "live_trading_enabled": False}
    monkeypatch.setenv("APCA_API_KEY_ID", "paper-key-123")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret-for-tests")
    monkeypatch.setenv("ALPACA_PAPER_EXPECTED_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setattr("agentic_trading.api.read_paper_account", read_mock)
    ok = app.get("/v1/paper/account")
    assert ok.status_code == 200
    assert ok.json()["paper_api_readable"] is True
    assert ok.headers["cache-control"] == "no-store"
    # No paper order route was added by S12.
    assert app.post("/v1/paper/orders", json={}).status_code == 404


def test_mixed_legacy_and_current_secrets_rejected(monkeypatch, tmp_path):
    for key in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY",
                "ALPACA_PAPER_API_KEY_ID", "ALPACA_PAPER_API_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APCA_API_KEY_ID", "new-key-only")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET_KEY", "older-secret")
    cfg = Settings(database_url=f"sqlite:///{tmp_path / 's12mix.db'}",
                   secret_key="D" * 48)
    engine, factory = new_session_factory(cfg.database_url)
    Base.metadata.create_all(engine)
    with factory() as session:
        session.add(CEO(email="ceo@example.test", password_hash=password_hash("long-test-password")))
        session.commit()
    engine.dispose()
    app = TestClient(create_app(cfg))
    login = app.post("/v1/auth/login", json={
        "email": "ceo@example.test", "password": "long-test-password"
    })
    assert login.status_code == 200
    snapshot = app.get("/v1/paper/account")
    assert snapshot.status_code == 200
    assert snapshot.json()["configured"] is False
