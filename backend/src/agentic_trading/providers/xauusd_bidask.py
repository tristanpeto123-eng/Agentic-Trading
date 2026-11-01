"""Read-only XAU/USD bid/ask research history from OANDA practice and Dukascopy.

No order routing. Provider access must be explicitly opted in; access or receipt
does not certify permission to store/retrain or make quotes executable.
M15 midpoint OHLC is only a model feature; simulated fills must use quote sides.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

import httpx

from agentic_trading.providers.dukascopy import (
    MinuteBar, ProviderError, aggregate_m15, collect,
)

UTC = timezone.utc
OANDA_PRACTICE = "https://api-fxpractice.oanda.com"
OANDA_PATH = "/v3/instruments/XAU_USD/candles"
MAX_RESPONSE_BYTES = 3 * 1024 * 1024
MAX_CANDLES = 2016  # About three weeks of M15 data, including closed sessions.


class QuoteSourceError(ValueError):
    """No validated paired bid/ask observations available."""


def _instant(text: object) -> datetime:
    if not isinstance(text, str) or not text.endswith(("Z", "+00:00")):
        raise QuoteSourceError("Quote timestamp must be UTC")
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QuoteSourceError("Invalid quote timestamp") from exc
    if value.utcoffset() != timedelta(0):
        raise QuoteSourceError("Quote timestamp must be UTC")
    return value.astimezone(UTC)


def _price(value: object, field: str) -> Decimal:
    if isinstance(value, (bool, dict, list)) or value is None:
        raise QuoteSourceError(f"Invalid {field}")
    try:
        number = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise QuoteSourceError(f"Invalid {field}") from exc
    if not number.is_finite() or not Decimal("200") <= number <= Decimal("20000"):
        raise QuoteSourceError(f"Implausible XAUUSD {field}")
    return number


def _quote(values: object, side: str) -> dict[str, Decimal]:
    if not isinstance(values, dict):
        raise QuoteSourceError(f"Missing {side} quote")
    result = {key: _price(values.get(source), f"{side}.{source}")
              for key, source in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))}
    if result["high"] < max(result["open"], result["close"], result["low"]):
        raise QuoteSourceError(f"Invalid {side} high")
    if result["low"] > min(result["open"], result["close"], result["high"]):
        raise QuoteSourceError(f"Invalid {side} low")
    return result


def _stamp(value: Decimal) -> str:
    return format(value, "f")


def _pair(timestamp: datetime, bid: dict[str, Decimal],
          ask: dict[str, Decimal], volume: object) -> dict:
    if timestamp.minute % 15 or timestamp.second or timestamp.microsecond:
        raise QuoteSourceError("M15 timestamp is not quarter-hour aligned")
    for key in ("open", "close"):
        if bid[key] > ask[key]:
            raise QuoteSourceError(f"Crossed bid/ask at {key}")
    mid = {key: _stamp((bid[key] + ask[key]) / 2)
           for key in ("open", "high", "low", "close")}
    # The high/low midpoint of two OHLC ranges is NOT a synchronized executable
    # price. Treat these strictly as chart/ML features.
    if Decimal(mid["high"]) < max(Decimal(mid["open"]), Decimal(mid["close"])):
        raise QuoteSourceError("Invalid midpoint high")
    if Decimal(mid["low"]) > min(Decimal(mid["open"]), Decimal(mid["close"])):
        raise QuoteSourceError("Invalid midpoint low")
    if isinstance(volume, bool) or isinstance(volume, (dict, list)):
        raise QuoteSourceError("Invalid quote volume")
    try:
        observed = Decimal(str(volume))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise QuoteSourceError("Invalid quote volume") from exc
    if not observed.is_finite() or observed < 0:
        raise QuoteSourceError("Invalid quote volume")
    return {
        "open_time": timestamp.isoformat().replace("+00:00", "Z"),
        "available_at": (timestamp + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
        **mid, "volume": _stamp(observed),
        "bid": {key: _stamp(bid[key]) for key in bid},
        "ask": {key: _stamp(ask[key]) for key in ask},
    }


def _snapshot(provider: str, rows: list[dict], *, source: str,
              provenance: dict | None = None) -> dict:
    if len(rows) < 96:
        raise QuoteSourceError("Fewer than 96 complete paired M15 observations")
    if len(rows) > MAX_CANDLES:
        rows = rows[-MAX_CANDLES:]
    previous = None
    gaps = 0
    for row in rows:
        stamp = _instant(row["open_time"])
        if previous is not None:
            if stamp <= previous:
                raise QuoteSourceError("Duplicate, reversed or unordered quote candles")
            if stamp - previous != timedelta(minutes=15):
                gaps += 1
        previous = stamp
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "market": "XAUUSD", "provider": provider, "source_url": source,
        "source_sha256": sha256(canonical).hexdigest(), "bars": rows,
        "gap_count": gaps, "price_basis": "bid_ask",
        "source_verified": False, "training_kind": "historical_policy_replay",
        "neural_training_performed": False, "persisted": False,
        "paper_trading_enabled": False, "live_trading_enabled": False,
        "provenance": provenance or {},
        "note": "Read-only, unqualified provider quotes; midpoint is for features, BID/ASK for hypothetical fills. No broker execution or data-use rights attested.",
    }


def parse_oanda_candles(payload: object, *, now: datetime) -> dict:
    if not isinstance(payload, dict) or payload.get("instrument") != "XAU_USD" or payload.get("granularity") != "M15":
        raise QuoteSourceError("Unexpected OANDA instrument or timeframe")
    candles = payload.get("candles")
    if not isinstance(candles, list) or len(candles) > 5000:
        raise QuoteSourceError("Invalid OANDA candle collection")
    rows = []
    for candle in candles:
        if not isinstance(candle, dict):
            raise QuoteSourceError("Invalid OANDA candle")
        if candle.get("complete") is not True:
            continue  # In-progress candles are never replayed.
        instant = _instant(candle.get("time"))
        if instant + timedelta(minutes=15) > now:
            raise QuoteSourceError("Future or still-open candle")
        rows.append(_pair(instant, _quote(candle.get("bid"), "bid"),
                          _quote(candle.get("ask"), "ask"), candle.get("volume", 0)))
    return _snapshot("OANDA v20 practice BID/ASK", rows,
                     source=OANDA_PRACTICE + OANDA_PATH)


def fetch_oanda_practice(*, token: str, now: datetime | None = None,
                         request: Callable | None = None) -> dict:
    """Use practice endpoint only. The secret never enters response/logs."""
    if not token or not token.strip():
        raise QuoteSourceError("OANDA practice research token not configured")
    clock = now or datetime.now(UTC)
    if clock.utcoffset() != timedelta(0):
        raise QuoteSourceError("OANDA clock must be UTC")
    params = {"price": "BA", "granularity": "M15", "count": str(MAX_CANDLES),
              "smooth": "false"}
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if request is None:
        def request(url, *, params, headers):
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                return client.get(url, params=params, headers=headers)
    try:
        response = request(OANDA_PRACTICE + OANDA_PATH, params=params, headers=headers)
        if response.status_code != 200:
            raise QuoteSourceError(f"OANDA practice returned HTTP {response.status_code}; check demo token and XAU_USD entitlement")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise QuoteSourceError("OANDA response exceeds import limit")
        payload = response.json()
    except QuoteSourceError:
        raise
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise QuoteSourceError("OANDA practice feed inaccessible or malformed") from exc
    return parse_oanda_candles(payload, now=clock)


def _tuple_quote(bar: tuple) -> dict[str, Decimal]:
    # aggregate_m15: time, open, high, low, close, volume
    return {"open": bar[1], "high": bar[2], "low": bar[3], "close": bar[4]}


def build_dukascopy_pairs(bars: dict[str, list[MinuteBar]],
                          provenance: dict, *, now: datetime) -> dict:
    grouped = {}
    for side in ("BID", "ASK"):
        m15, omitted = aggregate_m15(bars[side])
        grouped[side] = {row[0]: row for row in m15}
        if omitted:
            provenance = {**provenance, f"{side.lower()}_incomplete_m15": omitted}
    common = sorted(set(grouped["BID"]) & set(grouped["ASK"]))
    rows = []
    for timestamp in common:
        if timestamp + timedelta(minutes=15) > now:
            continue
        bid, ask = grouped["BID"][timestamp], grouped["ASK"][timestamp]
        rows.append(_pair(timestamp, _tuple_quote(bid), _tuple_quote(ask),
                          min(bid[5], ask[5])))
    return _snapshot("Dukascopy M1 BID/ASK → M15", rows,
                     source="https://datafeed.dukascopy.com/datafeed/",
                     provenance={**provenance, "paired_m15_candles": len(rows),
                                 "bid_only_windows": len(set(grouped["BID"]) - set(grouped["ASK"])),
                                 "ask_only_windows": len(set(grouped["ASK"]) - set(grouped["BID"]))})


def fetch_dukascopy_research(*, cache_dir: Path, now: datetime | None = None,
                             lookback_days: int = 10, download: bool = False,
                             fetch: Callable | None = None) -> dict:
    if not 3 <= lookback_days <= 21:
        raise QuoteSourceError("Dukascopy lookback must be 3–21 days")
    clock = now or datetime.now(UTC)
    if clock.utcoffset() != timedelta(0):
        raise QuoteSourceError("Dukascopy clock must be UTC")
    # Avoid the current, potentially unfinished UTC day. Weekends are skipped
    # by collect; missing weekdays remain recorded in provenance.
    end = clock.date()
    start = end - timedelta(days=lookback_days)
    args = {"cache_dir": cache_dir, "download": download, "clock": clock,
            "pause_seconds": 1.5}
    if fetch is not None:
        args["fetch"] = fetch
    try:
        bars, provenance = collect(start, end, **args)
        return build_dukascopy_pairs(bars, provenance, now=clock)
    except ProviderError as exc:
        raise QuoteSourceError(f"Dukascopy data unavailable: {exc}") from exc


def compare_sources(primary: dict, independent: dict) -> dict:
    """Informational discrepancy report. Never merge prices from two brokers."""
    lookup = {row["open_time"]: row for row in independent["bars"]}
    matched = [(row, lookup[row["open_time"]]) for row in primary["bars"]
               if row["open_time"] in lookup]
    if not matched:
        return {"matched": 0, "comparable": False}
    differences = [abs(Decimal(a["close"]) - Decimal(b["close"]))
                   for a, b in matched]
    return {"matched": len(matched), "comparable": True,
            "mean_absolute_mid_close_usd": _stamp(sum(differences) / len(differences)),
            "max_absolute_mid_close_usd": _stamp(max(differences)),
            "note": "Broker quote differences are expected; neither source is certified as ground truth."}
