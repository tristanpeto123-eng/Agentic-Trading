"""Owner-supplied historical archive ingestion: truthful provenance and native time header."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agentic_trading.data_engine import SourceManifest, ingest_csv, DataQualityError


DATE = datetime(2026, 10, 25, 10, tzinfo=timezone.utc)
CSV = ("time,open,high,low,close\n"
       "2026-10-23T10:00:00Z,4000,4002,3998,4001\n"
       "2026-10-23T10:15:00Z,4001,4003,3999,4002\n")


def manifest(**overrides):
    args = dict(
        provider="USER_SUPPLIED_UNVERIFIED", source_url=None,
        instrument="XAUUSD", timeframe="M15", price_basis="unknown",
        timezone="UTC", acquired_at=DATE,
        rights_reference="UNVERIFIED_OWNER_ARCHIVE",
        extraction_reference="User-provided XAUUSD history in Files",
        evidence_kind="historical",
    )
    args.update(overrides)
    return SourceManifest(**args)


def test_owner_native_time_csv_keeps_original_and_explicit_unverified_status():
    source = manifest()
    assert source.source_url is None
    assert source.price_basis == "unknown"
    candles, qc, canonical = ingest_csv(CSV, DATE)
    assert len(candles) == 2
    assert qc["rows"] == 2
    assert b"timestamp_open" not in canonical
    assert b"2026-10-23T10:00:00" in canonical


def test_named_provider_still_requires_real_https_source_url():
    with pytest.raises(ValidationError, match="HTTPS source URL"):
        manifest(provider="claimed provider", rights_reference="Documented agreement")
    with pytest.raises(ValidationError, match="UNVERIFIED_OWNER_ARCHIVE"):
        manifest(rights_reference="Documented agreement")
    assert manifest(
        provider="claimed provider",
        source_url="https://data.example.org/licensed.csv",
        rights_reference="Documented agreement",
    ).source_url == "https://data.example.org/licensed.csv"


def test_alias_does_not_permit_malformed_or_future_candles():
    with pytest.raises(DataQualityError, match="Expected exactly"):
        ingest_csv(CSV.replace("time,open", "time,timestamp_open,open"), DATE)
    with pytest.raises(DataQualityError, match="not closed"):
        ingest_csv(CSV.replace("2026-10-23T10:15:00Z", "2026-10-25T10:00:00Z"), DATE)
