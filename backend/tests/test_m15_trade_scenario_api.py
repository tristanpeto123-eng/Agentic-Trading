"""IPhone-backed saved archive -> hypothetical trade lab remains read-only."""
from sqlalchemy import func, select

from agentic_trading.storage import (
    Student, LearningPlan, TradeExperience, TrainingRun, ExamRun,
)
from test_historical_render import _setup, _source
from test_market_study_api import history


def test_saved_archive_has_read_only_cost_scenario_not_trading(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    with factory() as session:
        student = Student(name="Cost Study", name_key="cost study")
        session.add(student)
        session.flush()
        session.add(LearningPlan(
            student_id=student.id, version=1, mode="directed",
            markets=["XAUUSD"], skills=["range"], reason="Bounded research"))
        session.commit()
        student_id = student.id
    imported = client.post("/v1/datasets/import", headers=headers,
                           json={"source": _source(), "csv_content": history(1800)})
    assert imported.status_code == 201, imported.text
    dataset_id = imported.json()["id"]
    route = f"/v1/students/{student_id}/m15-trade-scenario"
    assert client.get(route).status_code == 422  # missing explicit dataset identifier
    response = client.get(route, params={"dataset_id": dataset_id})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["dataset_id"] == dataset_id
    assert report["student_id"] == student_id
    assert report["training"]["closed"] > 20
    assert {p["selected_rule"] for p in report["batches"]} == {"range"}
    assert report["assumed_costs"]["full_spread_usd_per_oz"] == "0.50"
    assert report["holdout_evaluated"] is False
    assert report["source_verified"] is False
    assert report["trade_execution_performed"] is False
    assert report["durable_trade_memory_written"] is False
    assert report["paper_trading_enabled"] is False
    assert report["live_trading_enabled"] is False
    with factory() as session:
        assert session.scalar(select(func.count(TradeExperience.id))) == 0
        assert session.scalar(select(func.count(TrainingRun.id))) == 0
        assert session.scalar(select(func.count(ExamRun.id))) == 0
    assert client.get(route, params={"dataset_id": "unknown"}).status_code == 404
    client.cookies.clear()
    assert client.get(route, params={"dataset_id": dataset_id}).status_code == 401
    engine.dispose()
