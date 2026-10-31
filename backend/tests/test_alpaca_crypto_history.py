"""Alpaca crypto historian: no execution, no silent data permission claims."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from agentic_trading.providers.alpaca_crypto_history import (
    CryptoDataError, fetch_private_btc_history,
)

UTC = timezone.utc
START = datetime(2026, 10, 20, tzinfo=UTC)
END = START + timedelta(days=1)
NOW = END + timedelta(days=2)


def bar(when="2026-10-20T00:00:00Z"):
    return {"t": when, "o": 90000, "h": 91000, "l": 89900, "c": 90500, "v": 0}


def quote(when="2026-10-20T00:00:00.000000123Z", bid=90000, ask=90020):
    return {"t": when, "bp": bid, "ap": ask, "bs": 0.5, "as": 0.4}


def client_from_pages(pages):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        payload = pages[min(len(calls) - 1, len(pages) - 1)]
        if isinstance(payload, int):
            return httpx.Response(payload, text="HTTP failure")
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_opt_in_and_utc_guards_run_before_any_http():
    client, calls = client_from_pages([])
    for params in ({}, {"allow_network": True},
                   {"private_research_acknowledged": True}):
        with pytest.raises(CryptoDataError, match="acknowledgements"):
            fetch_private_btc_history(start=START, end=END, now=NOW,
                                     client=client, **params)
    with pytest.raises(CryptoDataError, match="UTC"):
        fetch_private_btc_history(start=START.replace(tzinfo=None), end=END, now=NOW)
    assert calls == []


def test_valid_paged_bars_are_digested_not_qualified():
    pages = [
        {"bars": {"BTC/USD": [bar()]}, "next_page_token": "NEXT"},
        {"bars": {"BTC/USD": [bar("2026-10-20T01:00:00Z")]}, "next_page_token": None},
    ]
    client, calls = client_from_pages(pages)
    result = fetch_private_btc_history(
        start=START, end=END, now=NOW, client=client, allow_network=True,
        private_research_acknowledged=True)
    assert result.report["records"] == 2
    assert result.report["pages"] == 2
    assert "page_token=NEXT" in str(calls[-1].url)
    assert calls[0].url.host == "data.alpaca.markets"
    assert calls[0].method == "GET"
    assert len(result.report["canonical_sha256"]) == 64
    assert not result.report["market_data_rights_independently_verified"]
    assert not result.report["research_qualification_eligible"]
    assert not result.report["paper_trading_enabled"]
    assert result.canonical_jsonl.count(b"\n") == 2


def test_nanosecond_quote_timestamp_retained_and_spread_checked():
    client, _ = client_from_pages([{
        "quotes": {"BTC/USD": [quote(), quote("2026-10-20T00:00:00.000000456Z")]},
        "next_page_token": None
    }])
    result = fetch_private_btc_history(start=START, end=END, now=NOW, client=client,
                                       kind="quotes", timeframe="quote", allow_network=True,
                                       private_research_acknowledged=True)
    assert result.report["records"] == 2
    assert b"000000123" in result.canonical_jsonl
    assert result.report["min_indicative_spread_usd"] == "20"
    assert not result.report["commercial_use_authorized"]


@pytest.mark.parametrize("bad_page,pattern", [
    ({"bars": {"BTC/USD": [bar("2026-10-20T00:00:00Z"),
                           bar("2026-10-20T00:00:00Z")]}}, "Duplicate"),
    ({"bars": {"BTC/USD": [{"t": "2026-10-20T00:00:00Z",
                           "o": 100, "h": 99, "l": 98, "c": 100, "v": 2}]}}, "OHLC"),
    ({"quotes": {"BTC/USD": [quote(bid=90050, ask=90020)]}}, "Crossed"),
    ({"bars": {"ETH/USD": [bar()]}}, "Unexpected market"),
])
def test_invalid_records_and_wrong_instrument_fail_closed(bad_page, pattern):
    kind = "quotes" if "quotes" in bad_page else "bars"
    client, _ = client_from_pages([bad_page])
    with pytest.raises(CryptoDataError, match=pattern):
        fetch_private_btc_history(start=START, end=END, now=NOW, client=client,
            kind=kind, timeframe="quote" if kind == "quotes" else "1Hour",
            allow_network=True, private_research_acknowledged=True)


def test_provider_http_errors_and_repeated_page_tokens_fail_closed():
    client, _ = client_from_pages([429])
    with pytest.raises(CryptoDataError, match="HTTP 429"):
        fetch_private_btc_history(start=START, end=END, now=NOW, client=client,
            allow_network=True, private_research_acknowledged=True)
    pages = [
        {"bars": {"BTC/USD": [bar()]}, "next_page_token": "same"},
        {"bars": {"BTC/USD": [bar("2026-10-20T01:00:00Z")]}, "next_page_token": "same"},
    ]
    client, _ = client_from_pages(pages)
    with pytest.raises(CryptoDataError, match="repeating"):
        fetch_private_btc_history(start=START, end=END, now=NOW, client=client,
            allow_network=True, private_research_acknowledged=True)


def test_reject_future_and_overlong_quote_windows():
    client, _ = client_from_pages([{"bars": {"BTC/USD": [bar()]}}])
    with pytest.raises(CryptoDataError, match="unfinished"):
        fetch_private_btc_history(start=START, end=NOW+timedelta(days=1),
                                  now=NOW, client=client)
    with pytest.raises(CryptoDataError, match="Split long"):
        fetch_private_btc_history(start=START, end=END, now=NOW, client=client,
            kind="quotes", timeframe="quote")
