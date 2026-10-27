"""Imported PostgreSQL-backed XAUUSD candles reach an authenticated student lab.

Market studies are read-only and do not create trades, training checkpoints,
qualification decisions, or student promotions.
"""
from datetime import datetime, timedelta, timezone

from agentic_trading.storage import Student, LearningPlan, HistoricalDatasetArtifact
from test_historical_render import _setup, _source


def history(n=1800):
    start = datetime(2025, 4, 1, tzinfo=timezone.utc)
    lines = ["time,open,high,low,close"]
    for i in range(n):
        point = 3100 + (i // 25) / 7 + (i % 25) / 9
        when = start + timedelta(minutes=15 * i)
        lines.append(f"{when.isoformat().replace('+00:00','Z')},{point:.5f},{point + 1:.5f},{point - 1:.5f},{point + .25:.5f}")
    return "\n".join(lines) + "\n"


def test_authenticated_imported_candle_study_and_tamper_gate(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    with factory() as session:
        s = Student(name="Orion", name_key="orion")
        session.add(s)
        session.flush()
        session.add(LearningPlan(student_id=s.id, version=1, mode="directed",
                                 markets=["XAUUSD"], skills=["trend", "range"],
                                 reason="Owner research"))
        session.commit()
        sid = s.id
    imported = client.post("/v1/datasets/import", headers=headers, json={
        "source": _source(), "csv_content": history(),
    })
    assert imported.status_code == 201, imported.text
    dataset_id = imported.json()["id"]
    path = f"/v1/students/{sid}/candle-study"
    assert client.get(path).status_code == 200
    response = client.get(path, params={"dataset_id": dataset_id})
    assert response.status_code == 200, response.text
    study = response.json()
    assert study["student_id"] == sid
    assert study["dataset_id"] == dataset_id
    assert study["fixed_rules"] == ["trend", "range"]
    assert study["source_verified"] is False
    assert study["holdout_evaluated"] is False
    assert study["neural_training_performed"] is False
    assert study["trade_execution_performed"] is False
    assert study["paper_trading_enabled"] is False and study["live_trading_enabled"] is False
    assert study["batches"] and study["training_bars"] > 0
    assert client.get(f"/v1/students/not-a-student/candle-study").status_code == 404
    assert client.get(path, params={"dataset_id": "missing"}).status_code == 404
    client.cookies.clear()
    assert client.get(path).status_code == 401
    with factory() as session:
        blob = session.get(HistoricalDatasetArtifact, dataset_id)
        blob.canonical_jsonl = b"tampered-data"
        session.commit()
    engine.dispose()


def test_short_dataset_cannot_be_misrepresented_as_learning(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    with factory() as session:
        s = Student(name="Nova", name_key="nova")
        session.add(s); session.flush()
        session.add(LearningPlan(student_id=s.id, version=1, mode="autonomous",
                                 markets=[], skills=[], reason="Autonomous research"))
        session.commit()
        sid = s.id
    imported = client.post("/v1/datasets/import", headers=headers,
                           json={"source": _source(), "csv_content": history(24)})
    assert imported.status_code == 201
    result = client.get(f"/v1/students/{sid}/candle-study")
    assert result.status_code == 409
    assert "Chronological partition refused" in result.text
    engine.dispose()
