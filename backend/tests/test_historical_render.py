"""S12: durable historical replay uses PostgreSQL byte storage and stays quarantined.

The DB path is tested against a transactional SQLite engine substituted for the
PostgreSQL session factory. It verifies the same ORM persistence and API branch
without requiring hosted DB credentials in CI.
"""
from datetime import datetime, timezone
import importlib
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentic_trading.auth import password_hash
from agentic_trading.settings import Settings
from agentic_trading.sentinel import scan_health
from agentic_trading.storage import Base, CEO, HistoricalDatasetArtifact, HistoricalDataset, new_session_factory

api_module = importlib.import_module("agentic_trading.api")


def _dataset():
    rows = ["timestamp_open,open,high,low,close,volume"]
    for i in range(24):
        stamp = f"2025-04-07T{i // 4:02d}:{(i % 4) * 15:02d}:00Z"
        rows.append(f"{stamp},3000.00,3004.00,2997.00,3001.00,{i}")
    return "\n".join(rows) + "\n"


def _source():
    return {
        "provider": "Synthetic integration fixture", "source_url": "https://example.org/research",
        "instrument": "XAUUSD", "timeframe": "M15", "price_basis": "mid",
        "timezone": "UTC", "acquired_at": "2026-10-01T12:00:00Z",
        "rights_reference": "Synthetic fixture use only", "extraction_reference": "test-export-0001",
        "evidence_kind": "synthetic",
    }


def _setup(tmp_path, monkeypatch):
    db = f"sqlite:///{tmp_path / 'archive.sqlite3'}"
    engine, factory = new_session_factory(db)
    Base.metadata.create_all(engine)
    with factory() as s:
        s.add(CEO(email="ceo@example.org", password_hash=password_hash("strong-test-only-passphrase")))
        s.commit()
    # The production branch detects psycopg; map it to isolated in-memory-test
    # SQLite sessions without requiring a running PostgreSQL instance in CI.
    monkeypatch.setattr(api_module, "new_session_factory", lambda _url: (engine, factory))
    monkeypatch.setenv("PREVIEW_DISABLE_IMPORTS", "1")
    cfg = Settings("postgresql+psycopg://fake:no-network@localhost/archive", "s" * 48,
                   data_dir=str(tmp_path / "ephemeral"))
    c = TestClient(api_module.create_app(cfg))
    login = c.post("/v1/auth/login", json={
        "email": "ceo@example.org", "password": "strong-test-only-passphrase",
    })
    assert login.status_code == 200
    return c, {"X-CSRF-Token": login.json()["csrf_token"]}, factory, engine


def test_durable_import_candle_paging_source_integrity_and_reboot(tmp_path, monkeypatch):
    c, headers, factory, engine = _setup(tmp_path, monkeypatch)
    caps = c.get("/v1/capabilities").json()
    assert caps["historical_data_import_enabled"] is True
    assert caps["historical_candle_replay_enabled"] is True
    assert caps["historical_execution_enabled"] is False
    assert caps["paper_trading_enabled"] is False and caps["live_trading_enabled"] is False

    payload = {"source": _source(), "csv_content": _dataset()}
    assert c.post("/v1/datasets/import", json=payload).status_code == 403
    resp = c.post("/v1/datasets/import", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    record = resp.json()
    assert record["state"] == "quarantined" and not record["research_eligible"]
    assert record["quality_report"]["rows"] == 24
    assert c.post("/v1/datasets/import", headers=headers, json=payload).json()["id"] == record["id"]

    with factory() as session:
        row = session.get(HistoricalDataset, record["id"])
        saved = session.get(HistoricalDatasetArtifact, record["id"])
        assert row.raw_path == "db:historical_archive.v1"
        assert saved is not None
        assert sha256(saved.raw_csv).hexdigest() == row.source_hash
        assert sha256(saved.canonical_jsonl).hexdigest() == row.canonical_hash
        health = scan_health(session, data_root=tmp_path, checkpoints_root=tmp_path,
                             now=datetime(2026, 10, 26, tzinfo=timezone.utc))
        assert health["status"] == "research_safe"

    assert c.get(f"/v1/datasets/{record['id']}/candles").status_code == 200
    data = c.get(f"/v1/datasets/{record['id']}/candles", params={"limit": 20}).json()
    assert len(data["bars"]) == 20
    assert data["has_more"]
    assert data["bars"][-1]["open_time"] == "2025-04-07T05:45:00Z"
    assert data["source_verified"] is False
    assert data["historical_execution_enabled"] is False
    prev = c.get(f"/v1/datasets/{record['id']}/candles",
                 params={"limit": 20, "before": data["bars"][0]["open_time"]}).json()
    assert len(prev["bars"]) == 4
    assert not prev["has_more"]
    assert prev["bars"][0]["open_time"] == "2025-04-07T00:00:00Z"
    context = c.get(f"/v1/datasets/{record['id']}/context",
                    params={"as_of": "2025-04-07T01:00:00Z"}).json()
    assert len(context["m15"]) == 4
    assert len(context["h1"]) == 1 and context["research_eligible"] is False
    assert c.get(f"/v1/datasets/{record['id']}/candles", params={"limit": 1}).status_code == 422
    assert c.get(f"/v1/datasets/{record['id']}/candles", params={"before": "bad"}).status_code == 409
    assert TestClient(api_module.create_app(Settings(
        "postgresql+psycopg://fake:no-network@localhost/archive", "s"*48,
        data_dir=str(tmp_path / "ephemeral")
    ))).get(f"/v1/datasets/{record['id']}/candles").status_code == 401

    with factory() as session:
        artifact = session.get(HistoricalDatasetArtifact, record["id"])
        artifact.raw_csv = b"tampered"
        session.commit()
    assert c.get(f"/v1/datasets/{record['id']}/candles").status_code == 409
    with factory() as session:
        report = scan_health(session, data_root=tmp_path, checkpoints_root=tmp_path,
                             now=datetime(2026, 10, 26, tzinfo=timezone.utc))
        assert report["status"] == "blocked"
        assert any(f["reason"] == "historical_artifact_integrity" for f in report["findings"])
    engine.dispose()


def test_manual_force_disable_even_on_durable_db(tmp_path, monkeypatch):
    c, headers, _, engine = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("HISTORICAL_UPLOADS_FORCE_DISABLED", "1")
    disabled = TestClient(api_module.create_app(Settings(
        "postgresql+psycopg://fake:no-network@localhost/archive", "s"*48
    )))
    assert disabled.get("/v1/capabilities").json()["historical_data_import_enabled"] is False
    login = disabled.post("/v1/auth/login", json={
        "email": "ceo@example.org", "password": "strong-test-only-passphrase",
    })
    csrf = {"X-CSRF-Token": login.json()["csrf_token"]}
    assert disabled.post("/v1/datasets/import", headers=csrf,
                         json={"source": _source(), "csv_content": _dataset()}).status_code == 503
    engine.dispose()
