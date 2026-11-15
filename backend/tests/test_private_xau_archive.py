"""Private training archive integration; synthetic fixtures, no provider requests."""
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from agentic_trading.providers.private_xau_archive import SCHEMA, load_private_xau_archive
from agentic_trading.providers.xauusd_bidask import QuoteSourceError
from agentic_trading.storage import ResearchNeuralRun, TrainingRun
from test_historical_render import _setup
from test_one_click_training_source import add_student

api_module = importlib.import_module("agentic_trading.api")
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def archive(root: Path, count=1200):
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": SCHEMA, "partition": "train", "instrument": "XAUUSD",
                "timeframe": "M15", "source_url": "https://example.org/synthetic-archive",
                "training_end_utc_exclusive": (START + timedelta(minutes=count * 15)).isoformat()}
    for side, shift in (("bid", 0), ("ask", 0.4)):
        path = root / f"{side}.csv"
        with path.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(("time", "open", "high", "low", "close"))
            for i in range(count):
                value = 2500 + i * 0.1 + shift
                writer.writerow(((START + timedelta(minutes=i * 15)).isoformat(),
                                 value, value + 0.8, value - 0.6, value + 0.2))
        manifest[side] = {"path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


def write_manifest(path, manifest):
    path.write_text(json.dumps(manifest))


def test_paired_training_archive_keeps_unknown_volume_and_gaps(tmp_path):
    path, manifest = archive(tmp_path, 2050)
    # Remove the same candle on both sides; never manufacture a replacement.
    for side in ("bid", "ask"):
        csv_path = tmp_path / manifest[side]["path"]
        lines = csv_path.read_text().splitlines()
        del lines[101]
        csv_path.write_text("\n".join(lines) + "\n")
        manifest[side]["sha256"] = sha256(csv_path.read_bytes()).hexdigest()
    write_manifest(path, manifest)
    output = load_private_xau_archive(path, now=NOW)
    assert len(output["bars"]) == 2016
    assert output["gap_count"] == 1
    assert all(bar["volume"] is None for bar in output["bars"])
    assert output["bars"][0]["bid"]["open"] != output["bars"][0]["ask"]["open"]
    assert output["provenance"]["partition"] == "train"
    assert output["provenance"]["training_rows_available"] == 2049
    assert output["provenance"]["reserved_evaluation_rows_supplied"] is False
    assert output["source_verified"] is False
    assert output["paper_trading_enabled"] is False
    assert output["live_trading_enabled"] is False
    assert load_private_xau_archive(path, now=NOW)["source_sha256"] == output["source_sha256"]


@pytest.mark.parametrize("fault", ["tamper", "missing", "mismatch", "cross", "extra_column",
                                   "non_training", "cutoff", "future", "path_escape", "symlink_escape"])
def test_rejects_integrity_and_partition_errors(tmp_path, fault):
    root = tmp_path / "private"
    path, manifest = archive(root)
    side_path = root / "bid.csv"
    clock = NOW
    if fault == "tamper":
        side_path.write_text(side_path.read_text() + "\n")
    elif fault == "missing":
        side_path.unlink()
    elif fault in ("mismatch", "cross", "extra_column"):
        lines = side_path.read_text().splitlines()
        fields = lines[1].split(",")
        if fault == "mismatch":
            fields[0] = (START - timedelta(minutes=15)).isoformat()
        elif fault == "cross":
            fields[1:] = ["3000", "3001", "2999", "3000"]
        else:
            fields.append("unexpected")
        lines[1] = ",".join(fields)
        side_path.write_text("\n".join(lines) + "\n")
        manifest["bid"]["sha256"] = sha256(side_path.read_bytes()).hexdigest()
    elif fault == "non_training":
        manifest["partition"] = "sealed_test"
    elif fault == "cutoff":
        manifest["training_end_utc_exclusive"] = START.isoformat()
    elif fault == "future":
        clock = START
    else:
        external = tmp_path / "external.csv"
        external.write_bytes(side_path.read_bytes())
        if fault == "path_escape":
            manifest["bid"]["path"] = "../external.csv"
        else:
            side_path.unlink()
            side_path.symlink_to(external)
    write_manifest(path, manifest)
    with pytest.raises(QuoteSourceError):
        load_private_xau_archive(path, now=clock)


def test_one_click_private_source_starts_persistent_neural_research(tmp_path, monkeypatch):
    path, _ = archive(tmp_path / "private")
    monkeypatch.setenv("ATL_XAU_ARCHIVE_MANIFEST", str(path))
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    sid = add_student(factory, "Private Archive Student", "XAUUSD")
    def no_network(**kwargs):
        pytest.fail("Configured private training archive must not request an online source")
    monkeypatch.setenv("ATL_OANDA_PRACTICE_RESEARCH", "1")
    monkeypatch.setattr(api_module, "fetch_oanda_practice", no_network)
    source = client.get(f"/v1/students/{sid}/train-data")
    assert source.status_code == 200, source.text
    assert len(source.json()["bars"]) == 1200
    assert source.headers["cache-control"] == "no-store"
    with factory() as session:
        assert session.scalars(select(ResearchNeuralRun)).all() == []
        assert session.scalars(select(TrainingRun)).all() == []
    assert client.post(f"/v1/students/{sid}/neural/start").status_code == 403
    started = client.post(f"/v1/students/{sid}/neural/start", headers=headers)
    assert started.status_code == 200, started.text
    run_id = started.json()["run_id"]
    advanced = client.post(f"/v1/students/{sid}/neural/{run_id}/epoch",
                           headers=headers, json={"expected_epoch": 0})
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["epoch"] == 1
    with factory() as session:
        record = session.get(ResearchNeuralRun, run_id)
        assert record is not None
        assert record.frozen_examples["source_sha256"] == source.json()["source_sha256"]
    client.cookies.clear()
    assert client.get(f"/v1/students/{sid}/train-data").status_code == 401
    engine.dispose()


def test_configured_bad_archive_never_silently_changes_source(tmp_path, monkeypatch):
    monkeypatch.setenv("ATL_XAU_ARCHIVE_MANIFEST", str(tmp_path / "missing-manifest.json"))
    client, _, factory, engine = _setup(tmp_path, monkeypatch)
    sid = add_student(factory, "Broken Archive Student", "XAUUSD")
    monkeypatch.setenv("ATL_OANDA_PRACTICE_RESEARCH", "1")
    monkeypatch.setattr(api_module, "fetch_oanda_practice", lambda **_: pytest.fail("Source fallback"))
    result = client.get(f"/v1/students/{sid}/train-data")
    assert result.status_code == 409
    assert str(tmp_path) not in result.text
    engine.dispose()
