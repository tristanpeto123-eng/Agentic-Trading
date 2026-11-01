"""Opt-in CFD academy research foundation. No broker access, orders, or model promotion.

Keep triple-barrier y from autolabel.py unchanged. The separate ledger supplies
cost-adjusted net results for honest gates, while A/B/C/D stays chronological.
Requires pandas/numpy; intentionally not imported by the production web app.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Literal

import numpy as np
import pandas as pd

import autolabel


class FoundationError(ValueError):
    """Reject ambiguous quote/financing data or forbidden slice access."""


DATA_COLS = (
    "time", "open", "high", "low", "close", "volume", "spread",
    "financing_long", "financing_short",
)
STEP = pd.Timedelta(minutes=15)


@dataclass(frozen=True)
class CostContract:
    """Explicit **per unit of instrument** charges, not currency account P&L.

    Observed 'spread' is the full bid-ask spread in price units per M15 row.
    Observed 'financing_long' and 'financing_short' are booked charges per
    price unit for that bar (usually zero except broker rollover events).
    Slippage and commission are *per-side*, and independently sourced.
    """
    slippage_entry: Decimal
    slippage_exit: Decimal
    commission_per_side: Decimal
    source_reference: str
    price_basis: Literal["mid"] = "mid"

    def __post_init__(self):
        if self.price_basis != "mid":
            raise FoundationError("Cost ledger requires explicitly labelled mid OHLC")
        if len(self.source_reference.strip()) < 8:
            raise FoundationError("Cost source reference is required")
        for name in ("slippage_entry", "slippage_exit", "commission_per_side"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise FoundationError(f"{name} must be an explicit nonnegative finite Decimal")

    def audit(self):
        return {"slippage_entry": str(self.slippage_entry),
                "slippage_exit": str(self.slippage_exit),
                "commission_per_side": str(self.commission_per_side),
                "source_reference": self.source_reference, "price_basis": self.price_basis}


@dataclass(frozen=True)
class SliceManifest:
    dataset_sha256: str
    instrument: str
    timeframe: Literal["M15"]
    provider_reference: str
    rights_reference: str
    n_bars: int
    a_end: int
    b_end: int
    c_end: int
    gaps: int
    # Final D starts at c_end and is not available through any research-access route.
    qualified: Literal[False] = False

    def bounds(self, part: Literal["A", "B", "C", "D"]):
        return {
            "A": (0, self.a_end), "B": (self.a_end, self.b_end),
            "C": (self.b_end, self.c_end), "D": (self.c_end, self.n_bars),
        }[part]


def _digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


def validated_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Chronological UTC M15 mid OHLC with observed, per-bar execution costs.

    No sorting, forward filling, inferred spreads, or adjusted prices. Market
    closures are counted as gaps and remain gaps.
    """
    if set(raw.columns) != set(DATA_COLS):
        raise FoundationError("Requires exactly time,OHLC,volume,spread,financing_long,financing_short")
    if len(raw) < 100:
        raise FoundationError("At least 100 closed M15 bars are required")
    frame = raw.loc[:, list(DATA_COLS)].copy().reset_index(drop=True)
    stamps = []
    for item in frame["time"]:
        try:
            stamp = pd.Timestamp(item)
        except (ValueError, TypeError) as exc:
            raise FoundationError("Malformed timestamp") from exc
        if stamp.tzinfo is None or stamp.utcoffset() != pd.Timedelta(0):
            raise FoundationError("Every candle timestamp must explicitly be UTC")
        if stamp.minute % 15 or stamp.second or stamp.microsecond or stamp.nanosecond:
            raise FoundationError("M15 open times must align to UTC 15-minute intervals")
        stamps.append(stamp.tz_convert("UTC"))
    frame["time"] = pd.DatetimeIndex(stamps)
    times = frame["time"]
    diffs = times.diff().iloc[1:]
    if not (diffs > pd.Timedelta(0)).all():
        raise FoundationError("Timestamps must be unique and in the original ascending order")
    if not (diffs >= STEP).all() or not ((diffs / STEP) % 1 == 0).all():
        raise FoundationError("Timestamp gaps must be whole M15 intervals")
    for name in DATA_COLS[1:]:
        try:
            series = pd.to_numeric(frame[name], errors="raise").astype(float)
        except (ValueError, TypeError) as exc:
            raise FoundationError(f"Invalid numeric {name}") from exc
        if not np.isfinite(series).all() or (series < 0).any():
            raise FoundationError(f"{name} must be finite and nonnegative")
        if name in ("open", "high", "low", "close") and (series <= 0).any():
            raise FoundationError(f"{name} must be strictly positive")
        frame[name] = series
    if (frame.high < frame[["open", "low", "close"]].max(axis=1)).any():
        raise FoundationError("High below OHLC")
    if (frame.low > frame[["open", "high", "close"]].min(axis=1)).any():
        raise FoundationError("Low above OHLC")
    if (frame.spread <= 0).any():
        raise FoundationError("Observed CFD spread must be strictly positive; do not invent zero spread")
    return frame


def _hash_frame(frame: pd.DataFrame) -> str:
    values = frame.copy()
    values["time"] = values.time.dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    return sha256(values.to_csv(index=False, float_format="%.14g").encode("utf-8")).hexdigest()


def create_manifest(raw: pd.DataFrame, *, instrument: str,
                    provider_reference: str, rights_reference: str) -> SliceManifest:
    frame = validated_frame(raw)
    if not instrument.strip() or len(provider_reference.strip()) < 8 or len(rights_reference.strip()) < 8:
        raise FoundationError("Instrument, provider and data-rights references required")
    n = len(frame)
    a, b, c = n * 50 // 100, n * 75 // 100, n * 90 // 100
    return SliceManifest(
        dataset_sha256=_hash_frame(frame), instrument=instrument, timeframe="M15",
        provider_reference=provider_reference, rights_reference=rights_reference,
        n_bars=n, a_end=a, b_end=b, c_end=c,
        gaps=int((frame.time.diff().iloc[1:] != STEP).sum()),
    )


def research_partition(raw: pd.DataFrame, manifest: SliceManifest, *,
                       part: Literal["A", "B", "C"], purpose: str) -> pd.DataFrame:
    """Fail closed on stale data and forbidden role. D is never exposed here.

    A: skill training; B: bot training; C: model selection only. No implicit
    access to other slices, including warm-up: future feature design must not
    quietly broaden data access.
    """
    allowed = {"A": "skill_training", "B": "bot_training", "C": "selection"}
    if part not in allowed or purpose != allowed[part]:
        raise FoundationError("Slice role mismatch or sealed D requested")
    frame = validated_frame(raw)
    if _hash_frame(frame) != manifest.dataset_sha256 or len(frame) != manifest.n_bars:
        raise FoundationError("Immutable source hash mismatch")
    if (manifest.timeframe != "M15" or
        (manifest.a_end, manifest.b_end, manifest.c_end) !=
            (len(frame) * 50 // 100, len(frame) * 75 // 100, len(frame) * 90 // 100)):
        raise FoundationError("Tampered A/B/C/D boundaries")
    start, end = manifest.bounds(part)
    return frame.iloc[start:end].copy().reset_index(drop=True)


def label_cost_ledger(frame: pd.DataFrame, dataset: pd.DataFrame,
                      costs: CostContract) -> pd.DataFrame:
    """Add after-cost reporting, without altering the existing label `y`.

    `frame` is *only one authorised data slice*. Its `i`/`t_end` are local.
    TP/SL/timeout semantics and conservative stop-first priority are exactly
    as in autolabel.triple_barrier. A stop gapping past the trigger fills at
    the worse opening price. This is a mid-price proxy, NEVER a broker fill.
    """
    df = validated_frame(frame)
    if not {"y", "t_end", "i", "direction"}.issubset(dataset.columns):
        raise FoundationError("Explicit detector direction and original labels required")
    result = dataset.copy().reset_index(drop=True)
    a = autolabel.atr(df)
    audit = []
    for record in result.itertuples(index=False):
        i, end, y = int(record.i), int(record.t_end), float(record.y)
        entry_i = i + 1
        if not (0 <= i < entry_i <= end < len(df)) or not np.isfinite(y):
            raise FoundationError("A label crosses its source slice or is incomplete")
        # Verify entire signal-to-exit timeframe is real contiguous M15 data.
        observed = df.time.iloc[i:end + 1].diff().iloc[1:]
        if (observed != STEP).any():
            audit.append(None)
            continue
        direction = int(record.direction)
        if direction not in (-1, 1):
            raise FoundationError("The detector signal must be +1 or -1")
        atr = float(a.iloc[i])
        if not np.isfinite(atr) or atr <= 0:
            raise FoundationError("Invalid risk ATR at signal time")
        mid_entry = float(df.at[entry_i, "open"])
        mid_stop = mid_entry - direction * autolabel.SL_ATR * atr
        mid_tp = mid_entry + direction * autolabel.RR * atr
        if end >= entry_i + autolabel.HORIZON:
            raise FoundationError("Label extends beyond 24-bar horizon")
        exit_reason = "TIMEOUT"
        exit_mid = float(df.at[end, "close"])
        for k in range(entry_i, end + 1):
            hit_stop = (df.at[k, "low"] <= mid_stop if direction == 1 else df.at[k, "high"] >= mid_stop)
            hit_tp = (df.at[k, "high"] >= mid_tp if direction == 1 else df.at[k, "low"] <= mid_tp)
            if hit_stop:
                exit_reason = "STOP"
                exit_mid = min(mid_stop, float(df.at[k, "open"])) if direction == 1 else max(mid_stop, float(df.at[k, "open"]))
                break
            if hit_tp:
                exit_reason = "TP"
                exit_mid = mid_tp
                break
        if (exit_reason == "TP") != (y == 1) or k != end:
            raise FoundationError("Cost overlay would contradict original TP-first label")
        if exit_reason == "TIMEOUT" and end != entry_i + autolabel.HORIZON - 1:
            raise FoundationError("Timeout label ends before the specified 24-bar horizon")
        entry_spread = float(df.at[entry_i, "spread"]) / 2
        exit_spread = float(df.at[end, "spread"]) / 2
        spread_cost = entry_spread + exit_spread
        slip_cost = float(costs.slippage_entry + costs.slippage_exit)
        commission_cost = float(costs.commission_per_side * 2)
        fin_column = "financing_long" if direction == 1 else "financing_short"
        financing_cost = float(df.loc[entry_i:end, fin_column].sum())
        gross = direction * (exit_mid - mid_entry)
        total_cost = spread_cost + slip_cost + commission_cost + financing_cost
        net = gross - total_cost
        risk = autolabel.SL_ATR * atr
        audit.append({
            "entry_index": entry_i, "exit_index": end,
            "exit_reason": exit_reason, "mid_entry": mid_entry, "mid_exit": exit_mid,
            "gross_pnl_per_unit": gross, "spread_cost_per_unit": spread_cost,
            "slippage_cost_per_unit": slip_cost, "commission_cost_per_unit": commission_cost,
            "financing_cost_per_unit": financing_cost, "total_cost_per_unit": total_cost,
            "net_pnl_per_unit": net, "net_r": net / risk,
            "net_profitable": int(net > 0), "execution_model": "M15_MID_PROXY_UNVERIFIED",
        })
    cost_cols = ("entry_index", "exit_index", "exit_reason", "mid_entry", "mid_exit",
                 "gross_pnl_per_unit", "spread_cost_per_unit", "slippage_cost_per_unit",
                 "commission_cost_per_unit", "financing_cost_per_unit", "total_cost_per_unit",
                 "net_pnl_per_unit", "net_r", "net_profitable", "execution_model")
    if not any(x is not None for x in audit):
        return pd.DataFrame(columns=list(result.columns) + list(cost_cols))
    keep = [idx for idx, row in enumerate(audit) if row is not None]
    extra = pd.DataFrame([audit[i] for i in keep], columns=cost_cols)
    return pd.concat([result.iloc[keep].reset_index(drop=True), extra], axis=1)


def prepare_skill_A(raw: pd.DataFrame, manifest: SliceManifest, *,
                    skill: str, costs: CostContract) -> tuple[pd.DataFrame, dict]:
    """Only slice A enters the detector/labeller. B/C/D never materialised."""
    if skill not in autolabel.DETECTORS:
        raise FoundationError("Unsupported skill")
    subset = research_partition(raw, manifest, part="A", purpose="skill_training")
    ds = autolabel.build_dataset(subset, skill)
    ledger = label_cost_ledger(subset, ds, costs)
    report = {
        "schema": "cfd_skill_cost_audit.v1", "slice": "A",
        "instrument": manifest.instrument, "timeframe": manifest.timeframe,
        "source_sha256": manifest.dataset_sha256,
        "cost_contract_sha256": _digest(costs.audit()),
        "slice_bar_count": len(subset), "labels_total": len(ds),
        "labels_cost_audited": len(ledger),
        "labels_dropped_on_market_gaps": len(ds) - len(ledger),
        "gross_tp_first_win_rate": float(ledger.y.mean()) if len(ledger) else None,
        "net_profitable_rate": float(ledger.net_profitable.mean()) if len(ledger) else None,
        "net_r_sum": float(ledger.net_r.sum()) if len(ledger) else None,
        "cost_basis": "MID_OHLC_ESTIMATE_NON_EXECUTABLE",
        "qualification_allowed": False, "broker_execution_allowed": False,
        "note": "Gross y retained. Costs shown separately. Quote-midpoint M15 OHLC cannot establish actual bid/ask fills; no model may qualify from this report.",
    }
    return ledger, report
