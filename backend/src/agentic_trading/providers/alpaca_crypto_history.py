"""Opt-in Alpaca BTC/USD historical capture for PRIVATE research only.

Bars can contain quote-midpoint prices, not necessarily traded prices.
Quotes are L1 observations, not executable fills. Never authorise trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Literal
import json
import re
import httpx

UTC = timezone.utc
SYMBOL = "BTC/USD"
ORIGIN = "https://data.alpaca.markets"
BAR_PATH = "/v1beta3/crypto/us/bars"
QUOTE_PATH = "/v1beta3/crypto/us/quotes"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PAGES = 30
MAX_PAGE_SIZE = 1000
TIMESTAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?(Z|\+00:00)$")


class CryptoDataError(ValueError):
    """Malformed, unsafe, incomplete or unavailable market observations."""


@dataclass(frozen=True)
class PrivateCryptoSnapshot:
    report: dict
    canonical_jsonl: bytes


def _utc_instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise CryptoDataError("Missing UTC timestamp")
    match = TIMESTAMP.fullmatch(value)
    if match is None:
        raise CryptoDataError("Explicit UTC ISO timestamp required")
    try:
        base = datetime.fromisoformat(match.group(1) + "+00:00")
    except ValueError as exc:
        raise CryptoDataError("Invalid UTC date/time") from exc
    fraction = match.group(2) or ""
    return base + timedelta(microseconds=int(fraction[:6].ljust(6, "0"))) if fraction else base


def _number(value: object, field: str, *, positive: bool = True) -> str:
    if isinstance(value, bool) or isinstance(value, (list, dict)):
        raise CryptoDataError(f"Invalid {field}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CryptoDataError(f"Invalid {field}") from exc
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise CryptoDataError(f"Non-positive or nonfinite {field}")
    return str(number)


def _validated_record(record: object, *, kind: str,
                      start: datetime, end: datetime, now: datetime,
                      timeframe: str) -> tuple[datetime, dict]:
    if not isinstance(record, dict):
        raise CryptoDataError("Market record is not an object")
    stamp = _utc_instant(record.get("t"))
    if not start <= stamp < end or stamp >= now:
        raise CryptoDataError("Observation outside requested, completed UTC history")
    if kind == "bars":
        interval = (timedelta(minutes=15) if timeframe == "15Min" else
                    timedelta(hours=1) if timeframe == "1Hour" else timedelta(days=1))
        if stamp + interval > now:
            raise CryptoDataError("Unfinished bar rejected")
        values = {k: _number(record.get(k), k, positive=(k != "v"))
                  for k in ("o", "h", "l", "c", "v")}
        o, h, l, c = (Decimal(values[k]) for k in ("o", "h", "l", "c"))
        if h < max(o, c, l) or l > min(o, c, h):
            raise CryptoDataError("Impossible OHLC bounds")
    else:
        values = {k: _number(record.get(k), k) for k in ("bp", "ap")}
        if Decimal(values["bp"]) > Decimal(values["ap"]):
            raise CryptoDataError("Crossed BTC/USD level-one quotes")
        for field in ("bs", "as"):
            if field in record:
                values[field] = _number(record[field], field, positive=False)
    return stamp, {"t": record["t"], **values}


def _check_window(start: datetime, end: datetime, now: datetime,
                  *, kind: str, timeframe: str, limit: int) -> None:
    for stamp in (start, end, now):
        if not isinstance(stamp, datetime) or stamp.utcoffset() != timedelta(0):
            raise CryptoDataError("Time bounds must be explicit UTC")
    if not start < end <= now:
        raise CryptoDataError("Invalid or unfinished requested date range")
    if kind not in ("bars", "quotes"):
        raise CryptoDataError("Only bars and read-only quotes are permitted")
    if (kind == "bars" and timeframe not in ("15Min", "1Hour", "1Day")) or (
        kind == "quotes" and timeframe != "quote"):
        raise CryptoDataError("Unsupported aggregation or quote mode")
    ceiling = timedelta(days=31) if kind == "bars" else timedelta(minutes=30)
    if end - start > ceiling:
        raise CryptoDataError("Split long ranges into bounded private requests")
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
        raise CryptoDataError("Unsafe page limit")


def fetch_private_btc_history(
    *, start: datetime, end: datetime, kind: Literal["bars", "quotes"] = "bars",
    timeframe: str = "1Hour", allow_network: bool = False,
    private_research_acknowledged: bool = False,
    client: httpx.Client | None = None,
    now: datetime | None = None, limit: int = 1000,
) -> PrivateCryptoSnapshot:
    """Explicit opt-in, bounded GET-only paginated history; fail closed."""
    clock = now or datetime.now(UTC)
    _check_window(start, end, clock, kind=kind, timeframe=timeframe, limit=limit)
    if not allow_network or not private_research_acknowledged:
        raise CryptoDataError("Explicit network and private-use acknowledgements required")
    path = BAR_PATH if kind == "bars" else QUOTE_PATH
    params = {
        "symbols": SYMBOL,
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": (end - timedelta(microseconds=1)).isoformat().replace("+00:00", "Z"),
        "limit": limit, "sort": "asc",
    }
    if kind == "bars":
        params["timeframe"] = timeframe
    previous: datetime | None = None
    seen_tokens: set[str] = set()
    page_hashes: list[str] = []
    normalized: list[dict] = []
    min_spread: Decimal | None = None
    max_spread: Decimal | None = None
    pages = 0
    owns_client = client is None
    http = client or httpx.Client(follow_redirects=False)
    try:
        while pages < MAX_PAGES:
            try:
                reply = http.get(ORIGIN + path, params=params, timeout=15,
                                 follow_redirects=False)
            except httpx.HTTPError as exc:
                raise CryptoDataError("Alpaca historical request failed; no partial export") from exc
            if reply.status_code != 200:
                raise CryptoDataError(f"Alpaca historical HTTP {reply.status_code}; no partial export")
            raw = reply.content
            if len(raw) > MAX_RESPONSE_BYTES:
                raise CryptoDataError("Alpaca response exceeded safe page size")
            try:
                payload = reply.json()
            except ValueError as exc:
                raise CryptoDataError("Non-JSON Alpaca response") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get(kind), dict):
                raise CryptoDataError("Unexpected historical market-data envelope")
            source = payload[kind]
            rows = source.get(SYMBOL, [])
            if not isinstance(rows, list) or len(rows) > limit:
                raise CryptoDataError("Malformed or over-limit crypto history page")
            if source.keys() - {SYMBOL}:
                raise CryptoDataError("Unexpected market symbol in history response")
            page_hashes.append(sha256(raw).hexdigest())
            for observation in rows:
                stamp, record = _validated_record(
                    observation, kind=kind, start=start, end=end, now=clock,
                    timeframe=timeframe)
                if previous is not None and (
                    stamp < previous or (kind == "bars" and stamp == previous)):
                    raise CryptoDataError("Duplicate/out-of-order bar or descending quotes")
                previous = stamp
                if kind == "quotes":
                    spread = Decimal(record["ap"]) - Decimal(record["bp"])
                    min_spread = spread if min_spread is None else min(min_spread, spread)
                    max_spread = spread if max_spread is None else max(max_spread, spread)
                normalized.append(record)
            pages += 1
            token = payload.get("next_page_token")
            if token is None or token == "":
                break
            if not isinstance(token, str) or len(token) > 1024 or token in seen_tokens:
                raise CryptoDataError("Malformed or repeating pagination cursor")
            if not rows:
                raise CryptoDataError("Empty page with pagination cursor")
            seen_tokens.add(token)
            params["page_token"] = token
        else:
            raise CryptoDataError("Page safety ceiling reached; split interval before retry")
    finally:
        if owns_client:
            http.close()
    if not normalized:
        raise CryptoDataError("Alpaca returned no records; do not treat as complete coverage")
    canonical = b"".join((json.dumps(item, sort_keys=True, separators=(",", ":")) +
                          "\n").encode("utf-8") for item in normalized)
    report = {
        "schema": "private_alpaca_btc_capture.v1",
        "provider": "Alpaca", "symbol": SYMBOL, "kind": kind,
        "timeframe": timeframe if kind == "bars" else "level_one_quote",
        "source_endpoint": ORIGIN + path,
        "requested_start_utc": start.isoformat(),
        "requested_end_exclusive_utc": end.isoformat(),
        "acquisition_utc": clock.isoformat(),
        "records": len(normalized), "pages": pages,
        "first_utc": normalized[0]["t"], "last_utc": normalized[-1]["t"],
        "canonical_sha256": sha256(canonical).hexdigest(),
        "response_page_sha256": page_hashes,
        "min_indicative_spread_usd": str(min_spread) if min_spread is not None else None,
        "max_indicative_spread_usd": str(max_spread) if max_spread is not None else None,
        "closed_bar_and_structural_checks_passed": True,
        "market_data_rights_independently_verified": False,
        "commercial_use_authorized": False,
        "research_qualification_eligible": False,
        "trading_activation_authorized": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "note": "Private read-only quote research, not executable fills, licence clearance, model profitability or trading permission.",
    }
    return PrivateCryptoSnapshot(report, canonical)
