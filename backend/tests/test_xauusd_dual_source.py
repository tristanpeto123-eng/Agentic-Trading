"""ATL paired XAU/USD feed contract tests. No external network or account access."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib

import pytest

from agentic_trading.providers.dukascopy import MinuteBar
from agentic_trading.providers.xauusd_bidask import (
    QuoteSourceError, build_dukascopy_pairs, compare_sources,
    fetch_oanda_practice, parse_oanda_candles,
)
from agentic_trading.storage import LearningPlan, Student
from test_historical_render import _setup

UTC = timezone.utc
api_module = importlib.import_module("agentic_trading.api")
START = datetime(2026, 10, 1, tzinfo=UTC)
NOW = datetime(2026, 10, 27, tzinfo=UTC)


def oanda_payload(count=120):
    candles = []
    for i in range(count):
        instant = START + timedelta(minutes=i*15)
        p = Decimal("3000") + Decimal(i) / 100
        def side(base):
            return {"o": str(base), "h": str(base+1),
                    "l": str(base-1), "c": str(base+Decimal(".20"))}
        candles.append({
            "time": instant.isoformat().replace("+00:00", ".000000000Z"),
            "complete": True, "volume": 42,
            "bid": side(p), "ask": side(p+Decimal(".40"))
        })
    return {"instrument": "XAU_USD", "granularity": "M15", "candles": candles}


def test_oanda_parses_both_sides_with_no_future_and_stable_hash():
    a = parse_oanda_candles(oanda_payload(), now=NOW)
    b = parse_oanda_candles(oanda_payload(), now=NOW)
    assert a["source_sha256"] == b["source_sha256"]
    assert a["price_basis"] == "bid_ask"
    assert a["bars"][0]["bid"]["open"] == "3000"
    assert a["bars"][0]["ask"]["open"] == "3000.40"
    assert a["bars"][0]["open"] == "3000.20"
    assert a["bars"][0]["available_at"] == "2026-10-01T00:15:00Z"
    assert a["gap_count"] == 0
    assert a["live_trading_enabled"] is False
    assert a["source_verified"] is False


@pytest.mark.parametrize("mutation", ["cross", "duplicate", "future", "missing_ask", "bad_high"])
def test_oanda_rejects_unusable_quote_evidence(mutation):
    payload = oanda_payload()
    candles = payload["candles"]
    if mutation == "cross":
        candles[0]["ask"]["o"] = "2999"
    elif mutation == "duplicate":
        candles[1]["time"] = candles[0]["time"]
    elif mutation == "future":
        candles[0]["time"] = "2026-10-27T01:00:00.000000000Z"
    elif mutation == "missing_ask":
        del candles[0]["ask"]
    elif mutation == "bad_high":
        candles[0]["bid"]["h"] = "1000"
    with pytest.raises(QuoteSourceError):
        parse_oanda_candles(payload, now=NOW)


def test_oanda_omits_incomplete_last_candle():
    payload = oanda_payload()
    payload["candles"][-1]["complete"] = False
    data = parse_oanda_candles(payload, now=NOW)
    assert len(data["bars"]) == 119


def test_oanda_request_uses_practice_only_and_redacts_auth_error():
    seen = {}
    class BadResponse:
        status_code = 401
        content = b'{"message":"sensitive details"}'
    def request(url, *, params, headers):
        seen.update(url=url, params=params, headers=headers)
        return BadResponse()
    with pytest.raises(QuoteSourceError, match="HTTP 401") as err:
        fetch_oanda_practice(token="SECRET_EXAMPLE", now=NOW, request=request)
    assert "api-fxpractice.oanda.com" in seen["url"]
    assert seen["params"]["price"] == "BA"
    assert seen["params"]["granularity"] == "M15"
    assert "SECRET_EXAMPLE" not in str(err.value)


def test_dukascopy_reconciles_m1_bid_ask_without_invented_candles():
    bars = {"BID": [], "ASK": []}
    for i in range(96 * 15):
        t = START + timedelta(minutes=i)
        p = Decimal("3000") + Decimal(i)/Decimal("1000")
        for side, shift in (("BID", Decimal("0")), ("ASK", Decimal(".5"))):
            q = p+shift
            bars[side].append(MinuteBar(t, q, q+1, q-1, q+Decimal(".1"), Decimal("2")))
    result = build_dukascopy_pairs(bars, {"raw_sources": []}, now=NOW)
    assert len(result["bars"]) == 96
    assert result["bars"][0]["bid"]["open"] == "3000"
    assert result["bars"][0]["ask"]["open"] == "3000.5"
    assert result["bars"][0]["close"] != result["bars"][0]["bid"]["close"]
    assert result["persisted"] is False
    compared = compare_sources(result, result)
    assert compared["matched"] == 96
    assert compared["max_absolute_mid_close_usd"] == "0"


def add_student(factory, market="XAUUSD"):
    with factory() as session:
        student = Student(name="ATL Source Student", name_key="atl source student")
        session.add(student)
        session.flush()
        session.add(LearningPlan(student_id=student.id, version=1, mode="directed",
                                 markets=[market], skills=["trend"], reason="test only"))
        session.commit()
        return student.id


def test_one_click_uses_opted_in_oanda_and_optional_independent_crosscheck(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    student = add_student(factory)
    snap = parse_oanda_candles(oanda_payload(), now=NOW)
    secondary = {**snap, "provider": "Dukascopy independent"}
    monkeypatch.setenv("ATL_OANDA_PRACTICE_RESEARCH", "1")
    monkeypatch.setenv("ATL_DUKASCOPY_RESEARCH_DOWNLOAD", "1")
    monkeypatch.setenv("ATL_XAU_CROSSCHECK", "1")
    monkeypatch.setenv("OANDA_V20_PRACTICE_TOKEN", "not-a-real-key")
    called = []
    monkeypatch.setattr(api_module, "fetch_oanda_practice",
                        lambda *, token: called.append(("oanda", token)) or snap)
    monkeypatch.setattr(api_module, "fetch_dukascopy_research",
                        lambda **kwargs: called.append(("dukascopy", kwargs["download"])) or secondary)
    result = client.get(f"/v1/students/{student}/train-data")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["provider"] == "OANDA v20 practice BID/ASK"
    assert data["crosscheck"]["matched"] == 120
    assert data["crosscheck"]["max_absolute_mid_close_usd"] == "0"
    assert data["student_id"] == student
    assert result.headers["cache-control"] == "no-store"
    assert called == [("oanda", "not-a-real-key"), ("dukascopy", True)]
    client.cookies.clear()
    assert client.get(f"/v1/students/{student}/train-data").status_code == 401
    engine.dispose()


def test_one_click_dukascopy_fallback_when_oanda_fails(tmp_path, monkeypatch):
    client, headers, factory, engine = _setup(tmp_path, monkeypatch)
    student = add_student(factory)
    data = parse_oanda_candles(oanda_payload(), now=NOW)
    monkeypatch.setenv("ATL_OANDA_PRACTICE_RESEARCH", "1")
    monkeypatch.setenv("ATL_DUKASCOPY_RESEARCH_DOWNLOAD", "1")
    def failing(**kwargs):
        raise QuoteSourceError("practice endpoint not authorized")
    monkeypatch.setattr(api_module, "fetch_oanda_practice", failing)
    monkeypatch.setattr(api_module, "fetch_dukascopy_research",
                        lambda **kwargs: {**data, "provider": "Dukascopy M1 BID/ASK → M15"})
    result = client.get(f"/v1/students/{student}/train-data")
    assert result.status_code == 200, result.text
    assert result.json()["provider"].startswith("Dukascopy")
    engine.dispose()
