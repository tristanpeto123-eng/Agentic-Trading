"""Vendor adapter acceptance: no synthetic data is eligible; no interpolation."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import lzma
import struct

import pytest

from agentic_trading.data_engine import ingest_csv
from agentic_trading.providers.dukascopy import (
    ProviderError, aggregate_m15, build_export, cache_file, collect, decode_bi5,
    file_url, make_csv,
)

UTC = timezone.utc
DAY = date(2025, 10, 20)  # Monday


def make_archive(*, side="BID", minutes=15, start_sec=0):
    shift = 450 if side == "ASK" else 0
    raw = b"".join(struct.pack(">IIIIIf", start_sec + n * 60,
            4020000 + shift, 4020300 + shift, 4019800 + shift,
            4020500 + shift, 1.0) for n in range(minutes))
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


def test_urls_are_https_zero_indexed_month_and_side_restricted(tmp_path):
    assert file_url(DAY, "BID") == ("https://datafeed.dukascopy.com/datafeed/"
                                        "XAUUSD/2025/09/20/BID_candles_min_1.bi5")
    assert cache_file(tmp_path, DAY, "ASK").name == "ASK_candles_min_1.bi5"
    with pytest.raises(ProviderError):
        file_url(DAY, "MID")


def test_lzma_day_to_one_m15_and_no_invention():
    bars = decode_bi5(make_archive(), DAY)
    assert len(bars) == 15
    assert bars[0].open == 4020
    assert bars[0].high == 4020.5
    grouped, omitted = aggregate_m15(bars)
    assert len(grouped) == 1 and omitted == 0
    content = make_csv(grouped)
    candles, quality, _ = ingest_csv(content, datetime(2025, 10, 22, tzinfo=UTC))
    assert quality["research_eligible"] is False
    assert candles[0].available_at == datetime(2025, 10, 20, 0, 15, tzinfo=UTC)
    assert candles[0].volume == "15.0"
    broken = [x for i, x in enumerate(bars) if i != 2]
    grouped, omitted = aggregate_m15(broken)
    assert grouped == [] and omitted == 1


def test_reject_corruption_duplicate_seconds_incorrect_prices_and_oversize():
    with pytest.raises(ProviderError):
        decode_bi5(b"not lzma", DAY)
    with pytest.raises(ProviderError):
        decode_bi5(make_archive()[:-4], DAY)
    with pytest.raises(ProviderError):
        decode_bi5(make_archive(minutes=1) + b"garbage", DAY)
    with pytest.raises(ProviderError):
        decode_bi5(b"a" * (2 * 1024 * 1024 + 1), DAY)
    duplicate = struct.pack(">IIIIIf", 0, 4020000, 4020300, 4019800, 4020500, 1.0) * 2
    with pytest.raises(ProviderError):
        decode_bi5(lzma.compress(duplicate, format=lzma.FORMAT_ALONE), DAY)
    low_below = struct.pack(">IIIIIf", 0, 100, 100, 100, 100, 1.0)
    with pytest.raises(ProviderError):
        decode_bi5(lzma.compress(low_below, format=lzma.FORMAT_ALONE), DAY)


def test_local_cache_bid_ask_immutable_and_no_network(tmp_path):
    cache = tmp_path / "cache"
    for side in ("BID", "ASK"):
        file = cache_file(cache, DAY, side)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(make_archive(side=side))
    def must_not_call(_):
        raise AssertionError("Offline processing attempted HTTP")
    bars, report = collect(DAY, DAY + timedelta(days=1), cache_dir=cache,
                           fetch=must_not_call, clock=datetime(2026, 10, 25, tzinfo=UTC))
    assert report["missing_sources"] == [] and report["downloaded_requests"] == 0
    assert len(report["raw_sources"]) == 2
    assert len(bars["BID"]) == len(bars["ASK"]) == 15
    export, files = build_export(bars, report, acquired_at=datetime(2026, 10, 25, tzinfo=UTC))
    assert export["crossed_quote_minutes"] == []
    assert not export["research_eligible"] and not export["license_verified"]
    assert export["sides"]["BID"]["m15_count"] == 1
    assert hashlib.sha256(files["BID"].encode()).hexdigest() == export["sides"]["BID"]["csv_sha256"]
    assert "4020.45" in files["ASK"]


def test_missing_days_reported_and_temporary_network_failure_halts(tmp_path):
    end = DAY + timedelta(days=4)
    bars, report = collect(DAY, end, cache_dir=tmp_path / "empty", clock=datetime(2026, 10, 25, tzinfo=UTC))
    assert len(report["missing_sources"]) == 8
    assert all(not x for x in bars.values())
    def failing(_):
        raise ProviderError("HTTP 429")
    with pytest.raises(ProviderError, match="429"):
        collect(DAY, DAY+timedelta(days=1), cache_dir=tmp_path / "other",
                download=True, fetch=failing, clock=datetime(2026, 10, 25, tzinfo=UTC))
    with pytest.raises(ProviderError):
        collect(DAY, DAY + timedelta(days=401), cache_dir=tmp_path,
                clock=datetime(2026, 10, 25, tzinfo=UTC))


def test_download_is_opt_in_and_cached_files_decode_before_storage(tmp_path):
    calls = []
    def provider(url):
        calls.append(url)
        return make_archive(side="BID" if "BID" in url else "ASK")
    bars, report = collect(DAY, DAY+timedelta(days=1), cache_dir=tmp_path,
                           download=True, fetch=provider, pause_seconds=0,
                           clock=datetime(2026, 10, 25, tzinfo=UTC))
    assert report["downloaded_requests"] == 2 and len(calls) == 2
    assert len(bars["BID"]) == 15
    reloaded, again = collect(DAY, DAY+timedelta(days=1), cache_dir=tmp_path,
                              download=True, fetch=lambda _: pytest.fail("cache bypassed"),
                              clock=datetime(2026, 10, 25, tzinfo=UTC))
    assert again["downloaded_requests"] == 0 and reloaded == bars
    # Invalid feed archive is not cached.
    with pytest.raises(ProviderError):
        collect(DAY+timedelta(days=1), DAY+timedelta(days=2), cache_dir=tmp_path,
                download=True, fetch=lambda _: b"bad lzma", pause_seconds=0,
                clock=datetime(2026, 10, 25, tzinfo=UTC))
    assert not cache_file(tmp_path, DAY+timedelta(days=1), "BID").exists()


def test_detect_crossed_bid_ask_not_usable_for_execution():
    bid = decode_bi5(make_archive(side="ASK"), DAY)
    ask = decode_bi5(make_archive(side="BID"), DAY)
    report, _ = build_export({"BID": bid, "ASK": ask}, {"license_verified":False},
                             acquired_at=datetime(2025, 10, 22, tzinfo=UTC))
    assert len(report["crossed_quote_minutes"]) == 15
    assert not report["research_eligible"]
