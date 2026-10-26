"""Opt-in Dukascopy BID/ASK daily M1 `.bi5` to validated M15 research CSV.

Dukascopy is an external provider. This adapter does not establish or grant data
use rights. All exports remain quarantined and never imply research eligibility.
Raw records are retained for audit. Missing minutes are never fabricated.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
import json
import lzma
from pathlib import Path
import struct
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agentic_trading.data_engine import DataQualityError, ingest_csv

UTC = timezone.utc
RECORD = struct.Struct(">IIIIIf")  # seconds, open, close, low, high, volume
PRICE_DIVISOR = Decimal(1000)  # XAUUSD 3 decimal places; fail on implausible decode
MAX_COMPRESSED = 2 * 1024 * 1024
MAX_DECOMPRESSED = 2 * 1024 * 1024
USER_AGENT = "AgenticTrading-ResearchData/0.1 (manual, bounded retrieval)"
FEED = "https://datafeed.dukascopy.com/datafeed"
MAX_DAYS = 400


class ProviderError(DataQualityError):
    pass


@dataclass(frozen=True)
class MinuteBar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def file_url(day: date, side: str) -> str:
    if side not in {"BID", "ASK"}:
        raise ProviderError("side must be BID or ASK")
    return f"{FEED}/XAUUSD/{day.year:04d}/{day.month-1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"


def cache_file(cache_dir: Path, day: date, side: str) -> Path:
    if side not in {"BID", "ASK"}:
        raise ProviderError("side must be BID or ASK")
    return cache_dir / "XAUUSD" / f"{day.year:04d}" / f"{day.month-1:02d}" / f"{day.day:02d}" / f"{side}_candles_min_1.bi5"


def decode_bi5(payload: bytes, day: date) -> list[MinuteBar]:
    if not payload or len(payload) > MAX_COMPRESSED:
        raise ProviderError("Empty or oversized compressed day")
    try:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        decoded = decoder.decompress(payload, max_length=MAX_DECOMPRESSED + 1)
    except (lzma.LZMAError, EOFError, ValueError) as exc:
        raise ProviderError("Invalid LZMA day archive") from exc
    if not decoder.eof or decoder.unused_data or len(decoded) > MAX_DECOMPRESSED:
        raise ProviderError("Truncated, trailing, or overlarge LZMA data")
    if len(decoded) % RECORD.size:
        raise ProviderError("Day archive contains partial record")
    # A closed session can provide zero valid candles. Never invent prices.
    bars: list[MinuteBar] = []
    previous_seconds = -1
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    for sec, raw_open, raw_close, raw_low, raw_high, raw_volume in RECORD.iter_unpack(decoded):
        if sec >= 86400 or sec % 60 or sec <= previous_seconds:
            raise ProviderError("Minute timestamps out of range, unaligned, duplicate or unordered")
        previous_seconds = sec
        nums = [Decimal(raw) / PRICE_DIVISOR for raw in (raw_open, raw_high, raw_low, raw_close)]
        o, h, l, c = nums
        if any(x < 200 or x > 20000 for x in nums):
            raise ProviderError("Implausible XAUUSD price with required 1,000-point divisor")
        if l > min(o, h, c) or h < max(o, l, c):
            raise ProviderError("Bad OHLC record in feed")
        vol = Decimal(str(raw_volume))
        if not vol.is_finite() or vol < 0:
            raise ProviderError("Invalid quote volume")
        bars.append(MinuteBar(start + timedelta(seconds=sec), o, h, l, c, vol))
    return bars


def aggregate_m15(minutes: list[MinuteBar]) -> tuple[list[tuple], int]:
    """Only produce candles with all 15 individual M1 observations present."""
    groups: dict[datetime, list[MinuteBar]] = {}
    for bar in minutes:
        key = bar.timestamp.replace(minute=bar.timestamp.minute // 15 * 15)
        groups.setdefault(key, []).append(bar)
    complete = []
    missing_groups = 0
    for key, segment in sorted(groups.items()):
        expected = [key + timedelta(minutes=i) for i in range(15)]
        if [b.timestamp for b in segment] != expected:
            missing_groups += 1
            continue
        complete.append((key, segment[0].open, max(x.high for x in segment),
                         min(x.low for x in segment), segment[-1].close,
                         sum((x.volume for x in segment), Decimal(0))))
    return complete, missing_groups


def make_csv(candles: list[tuple]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["timestamp_open", "open", "high", "low", "close", "volume"])
    for t, o, h, l, c, v in candles:
        writer.writerow([t.isoformat().replace("+00:00", "Z"), *[format(x, "f") for x in (o, h, l, c, v)]])
    return output.getvalue()


def http_fetch(url: str) -> bytes | None:
    """HTTPS only, immutable fixed-host URL from file_url. HTTP 404 is missing."""
    if not url.startswith(FEED + "/XAUUSD/"):
        raise ProviderError("Untrusted provider address")
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    try:
        with urlopen(req, timeout=25) as response:
            if response.geturl() != url:  # no redirect to a different host
                raise ProviderError("Unexpected provider redirect")
            payload = response.read(MAX_COMPRESSED + 1)
            if len(payload) > MAX_COMPRESSED:
                raise ProviderError("Provider response too large")
            return payload
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise ProviderError(f"Provider HTTP {exc.code}; import paused, retry later") from exc
    except (TimeoutError, URLError) as exc:
        raise ProviderError("Provider unreachable; raw source unavailable") from exc


def _atomic_new_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ProviderError(f"Existing source changed: {path}")
        return
    # Do not silently overwrite source artifacts, including across processes.
    with path.open("xb") as writer:
        writer.write(payload)


def collect(
    start: date, end: date, *, cache_dir: Path, download: bool = False,
    fetch: Callable[[str], bytes | None] = http_fetch, pause_seconds: float = 1.5,
    clock: datetime | None = None,
) -> tuple[dict[str, list[MinuteBar]], dict]:
    """Date range inclusive-exclusive; offline by default, bounded, auditable.

    Remote 404s are missing-source evidence, not assumed market closures.
    Do not resume after a temporary provider failure without re-running.
    """
    today = (clock or datetime.now(UTC)).date()
    if start >= end or (end - start).days > MAX_DAYS or end > today:
        raise ProviderError("Range must be nonempty, <=400 days and end no later than UTC today")
    if pause_seconds < 0:
        raise ProviderError("Pause must be nonnegative")
    bars: dict[str, list[MinuteBar]] = {"BID": [], "ASK": []}
    sources: list[dict] = []
    missing: list[dict] = []
    requests_sent = 0
    for offset in range((end - start).days):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue  # weekends aren't certified trading sessions
        for side in ("BID", "ASK"):
            path = cache_file(cache_dir, day, side)
            url = file_url(day, side)
            if path.is_file():
                payload = path.read_bytes()
            elif download:
                if requests_sent:
                    time.sleep(pause_seconds)
                requests_sent += 1
                payload = fetch(url)
                if payload is None:
                    missing.append({"date": day.isoformat(), "side": side, "reason": "HTTP 404"})
                    continue
                decode_bi5(payload, day)  # reject corrupt source before caching
                _atomic_new_file(path, payload)
            else:
                missing.append({"date": day.isoformat(), "side": side, "reason": "not_cached"})
                continue
            day_bars = decode_bi5(payload, day)
            bars[side].extend(day_bars)
            sources.append({"url": url, "side": side, "date": day.isoformat(),
                            "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
                            "m1_rows": len(day_bars)})
    # Differing missing sides are not safe executable bid/ask spread evidence.
    return bars, {"provider": "Dukascopy", "instrument": "XAUUSD", "timeframe": "M1",
                  "from_utc": start.isoformat(), "to_utc_exclusive": end.isoformat(),
                  "raw_sources": sources, "missing_sources": missing,
                  "downloaded_requests": requests_sent,
                  "license_verified": False, "research_eligible": False}


def build_export(bars: dict[str, list[MinuteBar]], provenance: dict, *, acquired_at: datetime) -> tuple[dict, dict[str, str]]:
    if acquired_at.tzinfo is None or acquired_at.utcoffset() != timedelta(0):
        raise ProviderError("acquired_at must be UTC")
    summaries = {}
    files = {}
    for side in ("BID", "ASK"):
        m15, omitted = aggregate_m15(bars[side])
        csv_content = make_csv(m15)
        if not m15:
            raise ProviderError(f"No complete M15 {side} candles; nothing to import")
        _, quality, _ = ingest_csv(csv_content, acquired_at)
        files[side] = csv_content
        summaries[side] = {"m1_count": len(bars[side]), "m15_count": len(m15),
                           "incomplete_m15_windows_omitted": omitted,
                           "csv_sha256": hashlib.sha256(csv_content.encode()).hexdigest(),
                           "quality_report": quality}
    by_side = {side: {m.timestamp: m for m in bars[side]} for side in ("BID", "ASK")}
    overlap = set(by_side["BID"]) & set(by_side["ASK"])
    crossed = [t.isoformat() for t in sorted(overlap) if (by_side["BID"][t].open > by_side["ASK"][t].open
              or by_side["BID"][t].close > by_side["ASK"][t].close)]
    report = {**provenance, "generated_at": acquired_at.isoformat(), "sides": summaries,
              "crossed_quote_minutes": crossed[:100], "crossed_quote_minutes_truncated": len(crossed) > 100,
              "matched_m1_minutes": len(overlap),
              "research_eligible": False,
              "note": "Provider and permitted data-use verification required; no executable-price proof"}
    return report, files
