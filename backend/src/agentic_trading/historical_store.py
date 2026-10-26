"""Read/write immutable historical artifacts on disk or within PostgreSQL.

Research-only: data source remains quarantined and is NEVER eligible for model
qualification, paper/live trading, or after-cost P&L inference from M15 OHLC.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

from sqlalchemy.orm import Session

from agentic_trading.data_engine import Candle, DataQualityError, load_candles, parse_iso_utc
from agentic_trading.storage import HistoricalDataset, HistoricalDatasetArtifact

DATABASE_ARTIFACT_PATH = "db:historical_archive.v1"


def store_historical_artifacts(session: Session, dataset_id: str, original: bytes, canonical: bytes) -> None:
    """Save both streams atomically with dataset metadata in the caller's transaction."""
    session.add(HistoricalDatasetArtifact(
        dataset_id=dataset_id, raw_csv=original, canonical_jsonl=canonical
    ))


def source_bytes(session: Session, dataset: HistoricalDataset, root: Path) -> tuple[bytes, bytes]:
    """Read & validate both content-addressed artifacts without silent fallbacks."""
    if dataset.raw_path == DATABASE_ARTIFACT_PATH and dataset.canonical_path == DATABASE_ARTIFACT_PATH:
        artifact = session.get(HistoricalDatasetArtifact, dataset.id)
        if artifact is None:
            raise DataQualityError("Database historical artifact missing")
        source, canonical = bytes(artifact.raw_csv), bytes(artifact.canonical_jsonl)
    elif dataset.raw_path.startswith("db:") or dataset.canonical_path.startswith("db:"):
        raise DataQualityError("Unknown historical storage scheme")
    else:
        base = root.resolve()
        paths = [(base / p).resolve() for p in (dataset.raw_path, dataset.canonical_path)]
        if any(not p.is_relative_to(base) for p in paths):
            raise DataQualityError("Historical artifact path escapes storage root")
        try:
            source, canonical = (p.read_bytes() for p in paths)
        except OSError as exc:
            raise DataQualityError("Frozen historical artifact missing") from exc
    if sha256(source).hexdigest() != dataset.source_hash:
        raise DataQualityError("Raw historical source checksum mismatch")
    if sha256(canonical).hexdigest() != dataset.canonical_hash:
        raise DataQualityError("Frozen normalized dataset checksum mismatch")
    return source, canonical


def verified_candles(session: Session, dataset: HistoricalDataset, root: Path) -> list[Candle]:
    """Validate the saved bytes before exposing candle data to a CEO reader."""
    _, canonical = source_bytes(session, dataset, root)
    try:
        result = []
        for line in canonical.splitlines():
            payload = json.loads(line)
            result.append(Candle(
                open_time=parse_iso_utc(payload["open_time"]),
                open=payload["open"], high=payload["high"], low=payload["low"],
                close=payload["close"], volume=payload.get("volume"),
            ))
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise DataQualityError("Frozen historical data has invalid structure") from exc
    if len(result) != dataset.quality_report.get("rows"):
        raise DataQualityError("Historical row count changed")
    return result
