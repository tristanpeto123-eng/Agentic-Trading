"""One-click research training imports appropriate data, not a fake training model."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib
import json

from agentic_trading.providers.alpaca_crypto_history import PrivateCryptoSnapshot
from agentic_trading.storage import Student, LearningPlan
from test_historical_render import _setup, _source

api_module = importlib.import_module("agentic_trading.api")

def add_student(factory, name, market):
    with factory() as session:
        person = Student(name=name, name_key=name.casefold())
        session.add(person)
        session.flush()
        session.add(LearningPlan(student_id=person.id, version=1, mode="directed",
                                 markets=[market], skills=["trend"], reason="Research-only"))
        session.commit()
        return person.id

def xau_csv(n=110):
    origin = datetime(2025,4,7,tzinfo=timezone.utc)
    lines=["timestamp_open,open,high,low,close,volume"]
    for i in range(n):
        t=(origin+timedelta(minutes=i*15)).isoformat().replace("+00:00","Z")
        v=2500+i/20
        lines.append(f"{t},{v:.3f},{v+.4:.3f},{v-.4:.3f},{v+.1:.3f},50")
    return "\n".join(lines)+"\n"

def test_training_auto_uses_saved_xau_without_client_upload(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    sid = add_student(factory, "XauStudent", "XAUUSD")
    assert client.get(f"/v1/students/{sid}/train-data").status_code == 409
    upload=client.post("/v1/datasets/import",headers=headers,
        json={"source":_source(),"csv_content":xau_csv()})
    assert upload.status_code == 201, upload.text
    result=client.get(f"/v1/students/{sid}/train-data")
    assert result.status_code == 200, result.text
    obj=result.json()
    assert obj["market"]=="XAUUSD"
    assert len(obj["bars"]) == 110
    assert obj["training_kind"] == "historical_policy_replay"
    assert obj["neural_training_performed"] is False
    assert obj["paper_trading_enabled"] is False
    assert obj["live_trading_enabled"] is False
    assert obj["persisted"] is False
    assert result.headers["cache-control"]=="no-store"
    client.cookies.clear()
    assert client.get(f"/v1/students/{sid}/train-data").status_code == 401
    engine.dispose()

def test_training_btc_fetch_requires_no_broker_key_and_does_not_mutate_records(tmp_path,monkeypatch):
    client,headers,factory,engine = _setup(tmp_path,monkeypatch)
    sid=add_student(factory,"BtcStudent","BTCUSD")
    origin=datetime(2026,10,25,tzinfo=timezone.utc)
    records=[]
    for i in range(120):
        stamp=(origin+timedelta(minutes=i*15)).isoformat().replace("+00:00","Z")
        records.append({"t":stamp,"o":"60000","h":"60020","l":"59990","c":"60005","v":"3"})
    raw=b"".join((json.dumps(row)+"\n").encode() for row in records)
    calls=[]
    def mock_fetch(**kw):
        calls.append(kw)
        return PrivateCryptoSnapshot(report={"canonical_sha256":sha256(raw).hexdigest()},canonical_jsonl=raw)
    monkeypatch.setattr(api_module,"fetch_private_btc_history", mock_fetch)
    output=client.get(f"/v1/students/{sid}/train-data")
    assert output.status_code==200,output.text
    data=output.json()
    assert data["market"] == "BTCUSD"
    assert data["provider"] == "Alpaca public historical crypto bars"
    assert data["gap_count"]==0
    assert len(data["bars"])==120
    assert calls[0]["timeframe"] == "15Min"
    assert calls[0]["kind"] == "bars"
    assert data["neural_training_performed"] is False
    assert data["persisted"] is False
    with factory() as session:
        from sqlalchemy import select
        from agentic_trading.storage import TrainingRun, AcademyJob, TradeExperience
        assert session.scalars(select(TrainingRun)).all()==[]
        assert session.scalars(select(AcademyJob)).all()==[]
        assert session.scalars(select(TradeExperience)).all()==[]
    engine.dispose()
