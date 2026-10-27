"""Read-only Alpaca adapter and CEO/student access gates."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from agentic_trading.api import create_app
from agentic_trading.auth import password_hash
from agentic_trading.providers.alpaca_paper_readonly import (
    PaperPreviewError, preview_btc_paper,
)
from agentic_trading.settings import Settings
from agentic_trading.storage import Base, CEO, new_session_factory


ACCOUNT_ID = "paper-btc-test-account"


def mock_client(account_id=ACCOUNT_ID, status="ACTIVE", quote=True):
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"  # No order writes are possible.
        assert request.headers["APCA-API-KEY-ID"] == "test-paper-key"
        assert request.headers["APCA-API-SECRET-KEY"] == "test-paper-secret"
        if request.url.path == "/v2/account":
            assert request.url.host == "paper-api.alpaca.markets"
            return httpx.Response(200, json={
                "id": account_id, "status": status, "crypto_status": "ACTIVE",
                "currency": "USD", "equity": "200", "buying_power": "200",
            })
        if request.url.path == "/v2/positions":
            return httpx.Response(200, json=[])
        if request.url.path == "/v2/orders":
            assert request.url.params["status"] == "open"
            return httpx.Response(200, json=[])
        if request.url.path == "/v1beta3/crypto/us/latest/quotes":
            assert request.url.host == "data.alpaca.markets"
            assert request.url.params["symbols"] == "BTC/USD"
            return httpx.Response(200, json={"quotes": {
                "BTC/USD": {"bp": 70000, "ap": 70020, "t": "2026-10-27T19:00:00Z"}
            } if quote else {}})
        raise AssertionError("Unexpected request: " + str(request.url))
    return httpx.Client(transport=httpx.MockTransport(respond))


def test_snapshot_get_only_and_never_activates_trading():
    with mock_client() as client:
        value = preview_btc_paper(
            key_id="test-paper-key", secret_key="test-paper-secret",
            expected_account_id=ACCOUNT_ID, client=client,
        )
    assert value["account_verified"] is True
    assert value["clean_test_account"] is True
    assert value["btc_quote"]["bid"] == 70000
    assert value["paper_budget_usd"] == "200"
    assert value["broker_order_execution_enabled"] is False
    assert value["paper_trading_enabled"] is False


def test_expected_account_mismatch_fails_before_other_reads():
    with mock_client(account_id="other-account") as client:
        with pytest.raises(PaperPreviewError, match="identity mismatch"):
            preview_btc_paper(key_id="test-paper-key", secret_key="test-paper-secret",
                              expected_account_id=ACCOUNT_ID, client=client)


def test_inactive_account_and_missing_quote_fail_closed():
    with mock_client(status="INACTIVE") as client:
        with pytest.raises(PaperPreviewError, match="not active"):
            preview_btc_paper(key_id="test-paper-key", secret_key="test-paper-secret",
                              expected_account_id=ACCOUNT_ID, client=client)
    with mock_client(quote=False) as client:
        with pytest.raises(PaperPreviewError, match="bid/ask unavailable"):
            preview_btc_paper(key_id="test-paper-key", secret_key="test-paper-secret",
                              expected_account_id=ACCOUNT_ID, client=client)


def test_no_credentials_no_network_calls():
    with pytest.raises(PaperPreviewError, match="required"):
        preview_btc_paper(key_id="", secret_key="", expected_account_id="")


def test_ceo_and_btc_student_scope_protected(monkeypatch, tmp_path):
    for field in ("ALPACA_PAPER_API_KEY_ID", "ALPACA_PAPER_API_SECRET_KEY",
                  "ALPACA_PAPER_EXPECTED_ACCOUNT_ID"):
        monkeypatch.delenv(field, raising=False)
    cfg = Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", secret_key="B"*48)
    engine, factory = new_session_factory(cfg.database_url)
    Base.metadata.create_all(engine)
    with factory() as db:
        db.add(CEO(email="ceo@example.test", password_hash=password_hash("test-long-password")))
        db.commit()
    engine.dispose()
    client = TestClient(create_app(cfg))
    assert client.get("/v1/students/anything/paper/btc/diagnostics").status_code == 401
    login = client.post("/v1/auth/login", json={"email": "ceo@example.test",
                                                "password": "test-long-password"})
    csrf = {"X-CSRF-Token": login.json()["csrf_token"]}
    gold = client.post("/v1/students", json={
        "name": "Gold Student", "mode": "directed", "markets": ["XAUUSD"], "skills": ["trend"]
    }, headers=csrf).json()["id"]
    btc = client.post("/v1/students", json={
        "name": "BTC Student", "mode": "directed", "markets": ["BTCUSD"], "skills": ["trend"]
    }, headers=csrf).json()["id"]
    assert client.get(f"/v1/students/{gold}/paper/btc/diagnostics").status_code == 409
    no_secrets = client.get(f"/v1/students/{btc}/paper/btc/diagnostics")
    assert no_secrets.status_code == 200
    assert no_secrets.json()["broker_connected"] is False
    assert no_secrets.json()["paper_trading_enabled"] is False
    assert no_secrets.json()["reason"] == "paper_credentials_not_configured"
