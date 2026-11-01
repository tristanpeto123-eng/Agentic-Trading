"""Council S4 trace is real deterministic research, never invented neural orders."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentic_trading.research_trace import TraceBatchInput, inspect_trace_batch
from agentic_trading.storage import Student, LearningPlan
from test_historical_render import _setup


def fixture(n=96):
    origin = datetime(2025, 4, 7, tzinfo=timezone.utc)
    bars = []
    for i in range(n):
        price = 1800 + .4*i
        bars.append({
            "open_time": (origin + timedelta(minutes=15 * i)).isoformat(),
            "open": str(round(price, 5)),
            "high": str(round(price + .9, 5)),
            "low": str(round(price - .5, 5)),
            "close": str(round(price + .4, 5)),
        })
    return bars


def data(student=None, **overrides):
    body = {"student_id": str(student or uuid4()), "price_basis": "mid",
            "candles": fixture(), "first_index": 95, "last_index": 95}
    body.update(overrides)
    return body


def test_real_s4_trace_without_model_blocks_trade_and_guardian():
    payload = TraceBatchInput.model_validate(data())
    report = inspect_trace_batch(payload, permitted_skills={"trend", "range", "breakout"})
    current = report["observations"][0]
    assert report["engine"] == "EXISTING_S4_DETERMINISTIC_REFERENCE_PIPELINE"
    assert current["regime"]["market"] == "TREND_UP"
    assert current["candidate"]["direction"] == "LONG"
    assert current["candidate"]["tactic"] == "TREND_CONTINUATION"
    assert current["scout_b"] == "NOT_TRAINED_OR_BOUND"
    assert current["guardian"] == "NOT_EVALUATED"
    assert current["decision"] == "NO_TRADE"
    assert current["reason"] == "SCOUT_B_UNTRAINED"
    assert len(current["trace_sha256"]) == 64
    assert report["simulated_orders_created"] == 0
    assert report["paper_trading_enabled"] is False
    assert report["live_trading_enabled"] is False
    assert report == inspect_trace_batch(payload, permitted_skills={"trend", "range", "breakout"})


def test_student_plan_does_not_approve_mismatched_tactic():
    current = inspect_trace_batch(
        TraceBatchInput.model_validate(data()), permitted_skills={"breakout"}
    )["observations"][0]
    assert current["reason"] == "OUTSIDE_STUDENT_LEARNING_PLAN"
    assert current["candidate"]["plan_permitted"] is False
    assert current["decision"] == "NO_TRADE"


def test_missing_candles_and_history_gaps_fail_closed():
    rows = fixture()
    early = TraceBatchInput.model_validate(data(candles=rows[:18], first_index=17, last_index=17))
    obj = inspect_trace_batch(early, permitted_skills={"trend"})["observations"][0]
    assert obj["reason"] == "STRATEGIST_ABSTAINED"
    assert obj["regime"]["market"] == "UNCERTAIN"
    assert obj["candidate"] is None

    rows.pop(40)
    gap = TraceBatchInput.model_validate(data(candles=rows, first_index=94, last_index=94))
    obj = inspect_trace_batch(gap, permitted_skills={"trend"})["observations"][0]
    assert obj["state"] == "DATA_GAP"
    assert obj["candidate"] is None and obj["decision"] == "NO_TRADE"


def test_reject_future_duplicate_out_of_order_and_oversized_batches():
    rows = fixture()
    with pytest.raises(ValidationError):
        TraceBatchInput.model_validate(data(first_index=1, last_index=50))
    with pytest.raises(ValidationError):
        TraceBatchInput.model_validate(data(candles=rows + [rows[-1]]))
    with pytest.raises(ValidationError):
        TraceBatchInput.model_validate(data(candles=rows[::-1]))
    future = fixture()
    future[-1]["open_time"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        TraceBatchInput.model_validate(data(candles=future))


def test_ceo_only_endpoint_returns_trace_without_database_writes(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    with factory() as session:
        student = Student(name="Trace CEO Student", name_key="trace ceo student")
        session.add(student)
        session.flush()
        session.add(LearningPlan(student_id=student.id, version=1, mode="directed",
                                 markets=["XAUUSD"], skills=["trend"],
                                 reason="Read-only audit"))
        session.commit()
        sid = student.id
    payload = data(sid)
    assert client.post("/v1/research/decision-trace", json=payload).status_code == 403
    resp = client.post("/v1/research/decision-trace", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    doc = resp.json()
    assert doc["student_id"] == sid
    assert doc["source_verified"] is False
    assert doc["neural_checkpoint_inference_enabled"] is False
    assert resp.headers["cache-control"] == "no-store"
    with factory() as session:
        from agentic_trading.storage import TradeExperience, TrainingRun, ExamRun
        from sqlalchemy import select
        assert session.scalars(select(TradeExperience)).all() == []
        assert session.scalars(select(TrainingRun)).all() == []
        assert session.scalars(select(ExamRun)).all() == []
    client.cookies.clear()
    assert client.post("/v1/research/decision-trace", headers=headers, json=payload).status_code == 401
    engine.dispose()
