"""Persistent neural research training tests: real gradients, restarts and safety."""
from datetime import datetime, timedelta, timezone
import math
from uuid import uuid4

import pytest
from sqlalchemy import select

from agentic_trading.research_neural import (
    ResearchNeuralError, build_training_snapshot, create_run,
    get_run_report, train_one_epoch,
)
from agentic_trading.storage import Base, LearningPlan, ResearchNeuralEpoch, Student, new_session_factory
from test_historical_render import _setup, _source


def research_bars(n=1400):
    origin = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        # Historic synthetic test fixture only; no claim of profitable market data.
        center = 1900 + i * .03 + math.sin(i / 8) * 3
        o = center
        c = o + (2.0 if i % 3 == 0 else -2.0)
        rows.append({
            "open_time": (origin + timedelta(minutes=i*15)).isoformat().replace("+00:00", "Z"),
            "available_at": (origin + timedelta(minutes=(i+1)*15)).isoformat().replace("+00:00", "Z"),
            "open": str(o), "high": str(max(o,c)+1.1),
            "low": str(min(o,c)-1.1), "close": str(c), "volume": "40",
        })
    return rows


def make_student(factory, market="XAUUSD"):
    with factory() as session:
        student = Student(name="Neural Test Student", name_key="neural test student")
        session.add(student)
        session.flush()
        session.add(LearningPlan(student_id=student.id, version=1,
                    mode="directed", markets=[market], skills=["trend"], reason="Research only"))
        session.commit()
        return student.id


def test_frozen_snapshot_labels_only_train_development_never_holdout():
    bars = research_bars()
    frozen = build_training_snapshot(bars, market="XAUUSD", tactic="trend",
                                     source_sha256="a"*64, plan_version=1)
    assert frozen["schema"].endswith(".v1")
    assert frozen["holdout_fraction_unread"] == .2
    assert frozen["source_verified"] is False
    assert frozen["execution_cost_verified"] is False
    assert len(frozen["train"]) >= 80
    assert len(frozen["development"]) >= 20
    # Available label comes from the NEXT bar's close, never the signal candle.
    assert all(row["available"] > row["at"] for row in frozen["train"])
    dev_cut = bars[int(len(bars)*.8)-96]["open_time"]
    assert all(row["at"] < dev_cut for row in frozen["development"])
    assert all(len(row["f"]) == 8 for row in frozen["train"]+frozen["development"])
    assert all("profit" not in str(row["f"]) for row in frozen["train"])


def test_actual_weights_change_each_epoch_and_resume_after_engine_restart(tmp_path):
    db_url = "sqlite:///" + str(tmp_path / "neural.sqlite")
    engine, factory = new_session_factory(db_url)
    Base.metadata.create_all(engine)
    student_id = make_student(factory)
    with factory() as session:
        run = create_run(session, student_id, market="XAUUSD", tactic="trend",
                         plan_version=1, bars=research_bars(), source_sha256="a"*64)
        assert run["epoch"] == 0 and not run["weights_persisted"]
        first = train_one_epoch(session, student_id, run["run_id"], 0)
        second = train_one_epoch(session, student_id, run["run_id"], 1)
        assert second["epoch"] == 2
        assert second["weights_persisted"] and second["trained_neural_model"]
        assert first["latest_weights_sha256"] != second["latest_weights_sha256"]
        assert len(second["metrics"]) == 2
        assert all(math.isfinite(x["train_loss"]) and math.isfinite(x["development_loss"])
                   for x in second["metrics"])
        assert not second["independent_holdout_evaluated"]
        assert not second["paper_trading_enabled"]
        with pytest.raises(ResearchNeuralError, match="already advanced"):
            train_one_epoch(session, student_id, run["run_id"], 0)
    engine.dispose()
    engine2, factory2 = new_session_factory(db_url)
    with factory2() as session:
        restored = get_run_report(session, student_id)
        assert restored["epoch"] == 2
        assert restored["latest_weights_sha256"] == second["latest_weights_sha256"]
        continued = train_one_epoch(session, student_id, restored["run_id"], 2)
        assert continued["epoch"] == 3
        assert continued["latest_weights_sha256"] != restored["latest_weights_sha256"]
        other = str(uuid4())
        assert get_run_report(session, other) is None
        with pytest.raises(ResearchNeuralError, match="not found"):
            train_one_epoch(session, other, restored["run_id"], 3)
    engine2.dispose()


def test_checkpoint_tampering_rejected(tmp_path):
    engine, factory = new_session_factory("sqlite:///" + str(tmp_path / "tamper.sqlite"))
    Base.metadata.create_all(engine)
    student_id = make_student(factory)
    with factory() as session:
        run = create_run(session, student_id, market="XAUUSD", tactic="trend",
                         plan_version=1, bars=research_bars(), source_sha256="b"*64)
        train_one_epoch(session, student_id, run["run_id"], 0)
        cp = session.scalar(select(ResearchNeuralEpoch))
        cp.weights_npz = b"garbage"
        session.commit()
        with pytest.raises(ResearchNeuralError, match="checksum"):
            get_run_report(session, student_id)
        with pytest.raises(ResearchNeuralError, match="checksum"):
            train_one_epoch(session, student_id, run["run_id"], 1)
    engine.dispose()


def test_reject_future_bad_gaps_too_few_examples():
    bars = research_bars()
    with pytest.raises(ResearchNeuralError, match="650"):
        build_training_snapshot(bars[:100], market="XAUUSD", tactic="trend",
                                source_sha256="c"*64, plan_version=1)
    future = research_bars()
    future[-1]["open_time"] = "2099-01-01T00:00:00Z"
    with pytest.raises(ResearchNeuralError, match="Future"):
        build_training_snapshot(future, market="XAUUSD", tactic="trend",
                                source_sha256="c"*64, plan_version=1)
    broken = research_bars()
    broken[10]["high"] = "1"
    with pytest.raises(ResearchNeuralError, match="invalid"):
        build_training_snapshot(broken, market="XAUUSD", tactic="trend",
                                source_sha256="c"*64, plan_version=1)


def test_authenticated_neural_flow_no_broker_or_policy_write(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    student_id = make_student(factory)
    bars = research_bars()
    csv_lines = ["timestamp_open,open,high,low,close,volume"]
    csv_lines.extend(",".join([row["open_time"], row["open"], row["high"],
                               row["low"], row["close"], row["volume"]])
                     for row in bars)
    uploaded = client.post("/v1/datasets/import", headers=headers,
                           json={"source": _source(),
                                 "csv_content": "\n".join(csv_lines)+"\n"})
    assert uploaded.status_code == 201, uploaded.text
    base = "/v1/students/" + student_id + "/neural"
    assert client.get(base+"/latest").status_code == 200
    assert client.get(base+"/latest").json()["run"] is None
    assert client.post(base+"/start").status_code == 403
    started = client.post(base+"/start", headers=headers, json={})
    assert started.status_code == 200, started.text
    first = started.json()
    assert first["epoch"] == 0 and first["qualification"] == "unqualified"
    epoch = client.post(base+"/"+first["run_id"]+"/epoch",
                        headers=headers, json={"expected_epoch":0})
    assert epoch.status_code == 200, epoch.text
    report = epoch.json()
    assert report["epoch"] == 1 and report["weights_persisted"]
    assert report["paper_trading_enabled"] is False and report["live_trading_enabled"] is False
    assert client.post(base+"/"+first["run_id"]+"/epoch",
                       headers=headers, json={"expected_epoch":0}).status_code == 409
    assert client.post(base+"/"+first["run_id"]+"/epoch",
                       headers=headers, json={"expected_epoch":True}).status_code == 422
    assert client.get(base+"/latest").json()["run"]["epoch"] == 1
    resumed = client.post(base+"/start", headers=headers, json={})
    assert resumed.status_code == 200
    assert resumed.json()["run_id"] == first["run_id"]
    assert resumed.json()["snapshot_sha256"] == first["snapshot_sha256"]
    with factory() as session:
        from agentic_trading.storage import TradeExperience, ResearchPolicyCandidate
        assert session.scalars(select(TradeExperience)).all() == []
        assert session.scalars(select(ResearchPolicyCandidate)).all() == []
    client.cookies.clear()
    assert client.get(base+"/latest").status_code == 401
    engine.dispose()
