"""Consent-aware import and chronological split of third-party trader histories.

Imports authorized CSV exports supplied by the account holder or data licensor.
Never scrapes public profiles or infers a license from public visibility.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import math
from pathlib import Path

REQUIRED = ("trade_id", "instrument", "side", "entry_utc", "exit_utc",
            "entry_price", "exit_price", "net_pnl")


def _utc(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("timestamps must be explicitly UTC")
    return parsed


def import_trader_history(path: str | Path, *, trader_id: str,
                          source: str, permission_reference: str,
                          permitted_use: str) -> dict:
    if any(not isinstance(x, str) or not x.strip() for x in
           (trader_id, source, permission_reference, permitted_use)):
        raise ValueError("trader, source and explicit permission metadata required")
    if "train" not in permitted_use.lower() and "research" not in permitted_use.lower():
        raise ValueError("permission must explicitly cover training or research")
    raw = Path(path).read_bytes()
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or any(key not in reader.fieldnames for key in REQUIRED):
            raise ValueError("missing trade history fields")
        trades = []
        ids = set()
        for row in reader:
            if not row["trade_id"] or row["trade_id"] in ids:
                raise ValueError("missing or duplicate trade id")
            ids.add(row["trade_id"])
            if row["side"].upper() not in ("BUY", "SELL"):
                raise ValueError("side must be BUY or SELL")
            entry, exit_ = _utc(row["entry_utc"]), _utc(row["exit_utc"])
            if exit_ <= entry:
                raise ValueError("exit must be after entry")
            values = [float(row[key]) for key in ("entry_price", "exit_price", "net_pnl")]
            if not all(math.isfinite(x) for x in values) or min(values[:2]) <= 0:
                raise ValueError("invalid price or pnl")
            trades.append({"trade_id": row["trade_id"],
                           "instrument": row["instrument"].upper(),
                           "side": row["side"].upper(),
                           "entry_utc": entry.isoformat(),
                           "exit_utc": exit_.isoformat(),
                           "entry_price": values[0], "exit_price": values[1],
                           "net_pnl": values[2],
                           "outcome": "win" if values[2] > 0 else "loss" if values[2] < 0 else "flat"})
    trades.sort(key=lambda t: (t["entry_utc"], t["trade_id"]))
    return {"schema_version": 1, "trader_id": trader_id, "source": source,
            "permission_reference": permission_reference,
            "permitted_use": permitted_use,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "trades": trades, "source_verified": False,
            "permission_independently_verified": False,
            "execution_authorized": False}


def chronological_split(dataset: dict, *, train_fraction: float = 0.7) -> dict:
    """Split by entry time; purge training trades overlapping holdout start."""
    if not 0 < train_fraction < 1:
        raise ValueError("invalid train fraction")
    trades = dataset["trades"]
    if len(trades) < 3:
        raise ValueError("at least three trades required")
    boundary = int(len(trades) * train_fraction)
    if boundary == 0 or boundary >= len(trades):
        raise ValueError("empty chronological partition")
    cutoff = trades[boundary]["entry_utc"]
    train = [t for t in trades[:boundary] if t["exit_utc"] <= cutoff]
    test = trades[boundary:]
    return {"train": train, "holdout": test, "purged_overlap": boundary-len(train),
            "holdout_start_utc": cutoff, "execution_authorized": False}
