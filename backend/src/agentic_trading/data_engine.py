"""Sprint 2: fail-closed, immutable, point-in-time historical OHLC ingestion.

CSV is a provider transfer format, *not* proof of provenance. Every import remains
research-ineligible pending independent source/rights verification. Never fill gaps.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UTC = timezone.utc
STEP = timedelta(minutes=15)
MAX_CSV_BYTES = 12 * 1024 * 1024
MAX_ROWS = 80_000


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider: str = Field(min_length=3, max_length=120)
    source_url: str | None = Field(default=None, pattern=r"^https://", max_length=1000)
    instrument: Literal["XAUUSD"] = "XAUUSD"
    timeframe: Literal["M15"] = "M15"
    price_basis: Literal["bid", "ask", "mid", "trade", "unknown"]
    timezone: Literal["UTC"] = "UTC"
    acquired_at: datetime
    rights_reference: str = Field(min_length=8, max_length=500)
    extraction_reference: str = Field(min_length=3, max_length=500)
    evidence_kind: Literal["historical", "synthetic"] = "historical"

    @model_validator(mode="after")
    def require_provenance_for_named_provider(self):
        if self.provider != "USER_SUPPLIED_UNVERIFIED" and not self.source_url:
            raise ValueError("A documented provider requires an HTTPS source URL; alternatively declare USER_SUPPLIED_UNVERIFIED")
        if self.provider == "USER_SUPPLIED_UNVERIFIED" and self.rights_reference != "UNVERIFIED_OWNER_ARCHIVE":
            raise ValueError("Owner-unverified imports must explicitly declare UNVERIFIED_OWNER_ARCHIVE")
        return self

    @field_validator("acquired_at")
    @classmethod
    def acquired_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("acquired_at must include an explicit UTC timezone")
        if value > datetime.now(UTC) + timedelta(minutes=1):
            raise ValueError("acquired_at cannot be in the future")
        return value.astimezone(UTC)


class DatasetImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: SourceManifest
    csv_content: str = Field(min_length=40)

    @field_validator("csv_content")
    @classmethod
    def bounded_input(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_CSV_BYTES:
            raise ValueError("CSV exceeds 12MiB safe-import limit")
        return value


class DataQualityError(ValueError):
    pass


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: str
    high: str
    low: str
    close: str
    volume: str | None

    @property
    def available_at(self) -> datetime:
        return self.open_time + STEP

    def as_dict(self) -> dict:
        return {"open_time": self.open_time.isoformat().replace("+00:00", "Z"),
                "available_at": self.available_at.isoformat().replace("+00:00", "Z"),
                "open": self.open, "high": self.high, "low": self.low,
                "close": self.close, "volume": self.volume}


def parse_iso_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise DataQualityError("timestamp_open must use timezone-aware ISO 8601") from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise DataQualityError("timestamp_open must be explicitly UTC (Z or +00:00)")
    return dt.astimezone(UTC)


def positive_decimal(value: str, *, field: str, allow_zero: bool = False) -> str:
    try:
        v = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise DataQualityError(f"{field} must be a finite decimal") from exc
    if not v.is_finite() or v < 0 or (v == 0 and not allow_zero):
        raise DataQualityError(f"{field} must be {'nonnegative' if allow_zero else 'positive'}")
    return format(v, "f")


def ingest_csv(csv_content: str, acquired_at: datetime) -> tuple[list[Candle], dict, bytes]:
    """Strict CSV parsing and UTC canonicalization. Never impute or sort the input."""
    original = csv_content.encode("utf-8")
    if len(original) > MAX_CSV_BYTES:
        raise DataQualityError("CSV exceeds 12MiB safe-import limit")
    reader = csv.DictReader(io.StringIO(csv_content, newline=""), strict=True)
    names = reader.fieldnames or []
    timestamp_column = "timestamp_open" if "timestamp_open" in names else "time"
    required = {timestamp_column, "open", "high", "low", "close"}
    if set(names) not in (required, required | {"volume"}) or len(names) != len(set(names)):
        raise DataQualityError("Expected exactly (timestamp_open|time),open,high,low,close[,volume]")
    rows: list[Candle] = []
    gaps: list[dict] = []
    warnings: list[str] = []
    jump_alerts: list[dict] = []
    flat_alerts = 0
    flat_run = 0
    previous_close: Decimal | None = None
    previous: datetime | None = None
    for row_index, row in enumerate(reader, start=2):
        if row_index > MAX_ROWS + 1:
            raise DataQualityError("CSV exceeds the 80,000-candle import limit")
        try:
            if None in row or any(value is None for value in row.values()):
                raise DataQualityError("wrong number of columns")
            dt = parse_iso_utc(row[timestamp_column])
            if dt.minute % 15 != 0 or dt.second or dt.microsecond:
                raise DataQualityError("M15 candle timestamp must align to a UTC quarter hour")
            if dt + STEP > acquired_at:
                raise DataQualityError("candle is not closed at acquisition time")
            nums = {k: positive_decimal(row[k], field=k) for k in ["open", "high", "low", "close"]}
            if Decimal(nums["high"]) < max(Decimal(nums[x]) for x in ["open", "low", "close"]):
                raise DataQualityError("high is below OHLC values")
            if Decimal(nums["low"]) > min(Decimal(nums[x]) for x in ["open", "high", "close"]):
                raise DataQualityError("low is above OHLC values")
            volume = positive_decimal(row["volume"], field="volume", allow_zero=True) if "volume" in row and row["volume"].strip() else None
            if previous is not None:
                if dt <= previous:
                    raise DataQualityError("timestamps must be unique and strictly increasing; do not silently sort")
                delta = dt - previous
                if delta != STEP:
                    missing = int(delta.total_seconds() / STEP.total_seconds()) - 1
                    gaps.append({"after": previous.isoformat(), "before": dt.isoformat(), "missing_m15_slots": missing,
                                 "crosses_weekend": any((previous + STEP * n).weekday() >= 5 for n in (1, missing))})
            close = Decimal(nums["close"])
            if previous_close is not None and (abs(close / previous_close - 1) > Decimal("0.10")):
                jump_alerts.append({"at": dt.isoformat(), "move_ratio": str(close / previous_close - 1)})
            previous_close = close
            if nums["open"] == nums["high"] == nums["low"] == nums["close"]:
                flat_run += 1
                if flat_run == 12:
                    flat_alerts += 1
            else:
                flat_run = 0
            rows.append(Candle(dt, nums["open"], nums["high"], nums["low"], nums["close"], volume))
            previous = dt
        except (DataQualityError, KeyError, TypeError) as exc:
            raise DataQualityError(f"CSV row {row_index}: {exc}") from exc
    if not rows:
        raise DataQualityError("Dataset is empty")
    if jump_alerts:
        warnings.append("Unusually large adjacent close moves detected; review for source errors or shocks.")
    if flat_alerts:
        warnings.append("Runs of at least 12 flat OHLC candles detected; review possible stale quotes.")
    if len(gaps) > 0:
        warnings.append("Missing intervals detected. Gaps are preserved; no prices were manufactured.")
    if any(c.open_time.weekday() >= 5 for c in rows):
        warnings.append("Weekend timestamps present; check provider market-session calendar.")
    first = rows[0].open_time
    last_close = rows[-1].available_at
    coverage_days = (last_close - first).total_seconds() / 86400
    if coverage_days < 365:
        warnings.append("Less than 365 calendar days of coverage (target: at least 12 months).")
    if all(c.volume is None for c in rows):
        warnings.append("Volume was not supplied; cannot infer real traded volume.")
    canonical = b"".join((json.dumps(c.as_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8") for c in rows)
    quality = {"rows": len(rows), "first_open": first.isoformat(), "last_close": last_close.isoformat(),
               "calendar_days": round(coverage_days, 4), "gap_count": len(gaps), "gaps": gaps[:100],
               "gaps_truncated": len(gaps) > 100, "warnings": warnings,
               "large_move_alerts": jump_alerts[:100], "large_move_alerts_truncated": len(jump_alerts) > 100,
               "stale_quote_run_alerts": flat_alerts,
               "valid_ohlc": True, "strictly_ordered": True,
               "source_verified": False, "research_eligible": False}
    return rows, quality, canonical


def frozen_bytes(root: Path, digest: str, original: bytes, canonical: bytes) -> tuple[str, str]:
    """Store two immutable blobs, keyed by SHA-256. Re-import is idempotent."""
    folder = root / "sha256" / digest[:2] / digest
    folder.mkdir(parents=True, exist_ok=True)
    raw_path = folder / "source.csv"
    canonical_path = folder / "m15.jsonl"
    for path, content in [(raw_path, original), (canonical_path, canonical)]:
        if path.exists():
            if path.read_bytes() != content:
                raise DataQualityError("Content-addressed artifact conflict; refusing overwrite")
            continue
        with NamedTemporaryFile(mode="wb", dir=folder, delete=False) as f:
            temp_path = Path(f.name)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        try:
            # Atomic creation with no existing-file overwrite, then remove temp.
            os.link(temp_path, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise DataQualityError("Concurrent artifact conflict; refusing overwrite")
        finally:
            temp_path.unlink(missing_ok=True)
    return str(raw_path.relative_to(root)), str(canonical_path.relative_to(root))


def completed_aggregates(candles: list[Candle], as_of: datetime, window_minutes: int) -> list[dict]:
    """Only full UTC-aligned closed HTF windows can be returned at as_of."""
    count = window_minutes // 15
    grouped: dict[datetime, list[Candle]] = {}
    for bar in candles:
        if bar.available_at > as_of:
            continue
        start_hour = (bar.open_time.hour * 60 + bar.open_time.minute) // window_minutes * window_minutes
        start = bar.open_time.replace(hour=start_hour // 60, minute=start_hour % 60, second=0, microsecond=0)
        grouped.setdefault(start, []).append(bar)
    output = []
    for start in sorted(grouped):
        rows = grouped[start]
        end = start + timedelta(minutes=window_minutes)
        if end > as_of or len(rows) != count:
            continue
        if any(row.open_time != start + STEP * index for index, row in enumerate(rows)):
            continue
        output.append({"open_time": start.isoformat(), "available_at": end.isoformat(),
                       "open": rows[0].open, "high": str(max(Decimal(r.high) for r in rows)),
                       "low": str(min(Decimal(r.low) for r in rows)), "close": rows[-1].close,
                       "volume": str(sum(Decimal(r.volume) for r in rows)) if all(r.volume is not None for r in rows) else None})
    return output


def load_candles(root: Path, relative_path: str, expected_hash: str) -> list[Candle]:
    """Verify frozen normalized artifact before use; corruption fails closed."""
    path = root / relative_path
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise DataQualityError("Frozen normalized dataset checksum mismatch")
    result = []
    for line in raw.splitlines():
        obj = json.loads(line)
        result.append(Candle(open_time=parse_iso_utc(obj["open_time"]), open=obj["open"], high=obj["high"],
                             low=obj["low"], close=obj["close"], volume=obj["volume"]))
    return result
