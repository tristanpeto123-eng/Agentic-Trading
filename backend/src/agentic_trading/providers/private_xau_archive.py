"""Hash-pinned, training-only local XAUUSD paired M15 research archive.

The server configuration selects a private manifest. Requests cannot choose
filesystem paths, download prices, or promote source/model qualification.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
from itertools import zip_longest
import json
from pathlib import Path
from urllib.parse import urlsplit

from agentic_trading.providers.xauusd_bidask import (
    QuoteSourceError, _instant, _pair, _quote, _snapshot,
)

SCHEMA = "private_xauusd_training_archive.v1"
MAX_MANIFEST_BYTES = 16_384
MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_ROWS = 80_000
FIELDS = ["time", "open", "high", "low", "close"]


def _read(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if not data or len(data) > limit:
        raise QuoteSourceError("Private XAUUSD archive file is empty or oversized")
    return data


def _source(root: Path, entry: object) -> tuple[bytes, str]:
    if not isinstance(entry, dict):
        raise QuoteSourceError("Missing private XAUUSD quote side")
    name, digest = entry.get("path"), entry.get("sha256")
    if (not isinstance(name, str) or not name or Path(name).is_absolute()
            or not isinstance(digest, str) or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)):
        raise QuoteSourceError("Invalid private XAUUSD source reference")
    target = (root / name).resolve()
    if not target.is_relative_to(root):
        raise QuoteSourceError("Private XAUUSD source must remain inside its archive directory")
    data = _read(target, MAX_SOURCE_BYTES)
    if sha256(data).hexdigest() != digest:
        raise QuoteSourceError("Private XAUUSD archive checksum mismatch")
    return data, digest


def load_private_xau_archive(manifest_path: Path, *, now: datetime | None = None) -> dict:
    """Read only dedicated TRAIN files, never a full archive or reserved folds.

    Bounds and UTC OHLC validation apply to every supplied training row before
    selecting the latest bounded window. Volume stays unknown, never invented.
    Partition metadata is an operator assertion, not independent qualification.
    """
    try:
        manifest_path = manifest_path.resolve()
        raw_manifest = _read(manifest_path, MAX_MANIFEST_BYTES)
        manifest = json.loads(raw_manifest)
        if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
                or manifest.get("partition") != "train"
                or manifest.get("instrument") != "XAUUSD"
                or manifest.get("timeframe") != "M15"):
            raise QuoteSourceError("Expected a training-only XAUUSD M15 archive manifest")
        source = manifest.get("source_url")
        if not isinstance(source, str):
            raise QuoteSourceError("Missing private XAUUSD source URL")
        address = urlsplit(source)
        if address.scheme != "https" or not address.hostname or address.username or address.password:
            raise QuoteSourceError("Private XAUUSD source URL must be public HTTPS provenance")
        cutoff = _instant(manifest.get("training_end_utc_exclusive"))
        clock = now or datetime.now(timezone.utc)
        if clock.utcoffset() != timedelta(0):
            raise QuoteSourceError("Private XAUUSD archive clock must be UTC")
        contents, hashes = {}, {}
        for side in ("bid", "ask"):
            contents[side], hashes[side] = _source(manifest_path.parent, manifest.get(side))
        readers = [csv.DictReader(io.StringIO(contents[side].decode("utf-8-sig")))
                   for side in ("bid", "ask")]
        if any(reader.fieldnames != FIELDS for reader in readers):
            raise QuoteSourceError("Expected time,open,high,low,close archive columns")
        bars = []
        previous = None
        for index, (bid, ask) in enumerate(zip_longest(*readers), start=1):
            if index > MAX_ROWS:
                raise QuoteSourceError("Private XAUUSD archive exceeds row limit")
            if bid is None or ask is None or bid.get("time") != ask.get("time"):
                raise QuoteSourceError("Private XAUUSD BID/ASK timestamps do not match")
            if set(bid) != set(FIELDS) or set(ask) != set(FIELDS):
                raise QuoteSourceError("Malformed private XAUUSD archive row")
            instant = _instant(bid["time"])
            if instant + timedelta(minutes=15) > min(cutoff, clock):
                raise QuoteSourceError("Private XAUUSD archive contains future or non-training candles")
            if previous is not None and instant <= previous:
                raise QuoteSourceError("Private XAUUSD archive timestamps must be strictly ordered")
            previous = instant
            quotes = [_quote({code: row.get(field) for code, field in
                             (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))}, side)
                      for row, side in ((bid, "bid"), (ask, "ask"))]
            if any(quotes[0][field] > quotes[1][field] for field in ("open", "high", "low", "close")):
                raise QuoteSourceError("Crossed private XAUUSD quote sides")
            bars.append(_pair(instant, *quotes, volume=None))
        result = _snapshot("Public XAUUSD BID/ASK archive (unverified)", bars, source=source,
                           provenance={"archive_manifest_sha256": sha256(raw_manifest).hexdigest(),
                                       "bid_csv_sha256": hashes["bid"], "ask_csv_sha256": hashes["ask"],
                                       "partition": "train", "training_rows_available": len(bars),
                                       "training_end_utc_exclusive": cutoff.isoformat(),
                                       "reserved_evaluation_rows_supplied": False,
                                       "license_verified": False})
        result["note"] = (
            "Private training-only archive; screened historical BID/ASK candles. "
            "Reserved evaluation files are not loaded. Gaps and unknown volume are preserved. "
            "Midpoint OHLC is for model features; fills and source authenticity remain unverified."
        )
        return result
    except QuoteSourceError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        # Keep private paths and file contents out of API error messages.
        raise QuoteSourceError("Private XAUUSD archive is unavailable or malformed") from exc
