"""Isolated point-in-time entry/exit research against a no-trade baseline.

Offline only; requires provenance metadata, not a verified vendor licence.
Candidate comparisons are strictly train-only and one frozen candidate is
diagnosed once on a disjoint development slice. Final 20% stays unexamined.
No fitted network, margin simulator, order routes or authority are created.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path

from .data_qualification import QualificationError
from .pair_qualification import qualify_pair, _rows


@dataclass(frozen=True)
class EntryExitPlan:
    lookback: int = 5
    holding: int = 3
    latency: int = 1
    quantity: float = 0.1
    commission_per_side: float = 0.05
    slippage_per_side: float = 0.2
    min_training_trades: int = 3


# Committed candidate list, never learned or tuned on the diagnostic slice.
RULES = ("MOMENTUM", "REVERSAL")
THRESHOLDS = (0.25, 0.5, 0.75, 1.5)


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _check_plan(plan: EntryExitPlan) -> None:
    if not isinstance(plan, EntryExitPlan):
        raise QualificationError("expected EntryExitPlan")
    for key, lo, hi in (("lookback", 2, 30), ("holding", 1, 30),
                        ("latency", 1, 10), ("min_training_trades", 1, 100)):
        value = getattr(plan, key)
        if type(value) is not int or not lo <= value <= hi:
            raise QualificationError(f"invalid research plan: {key}")
    for key, lo, hi in (("quantity", 0.001, 1.0),
                        ("commission_per_side", 0.0, 10.0),
                        ("slippage_per_side", 0.0, 10.0)):
        value = getattr(plan, key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise QualificationError(f"invalid research plan: {key}")


def _replay(
    bid: list[tuple], ask: list[tuple], *,
    start: int, stop: int, plan: EntryExitPlan, rule: str, threshold: float,
) -> dict:
    """Decide using closed bars <=i and fill at OPEN of i+1+latency.

    No concurrent positions. The lookback and all subsequent entry/exit bars
    must remain entirely inside [start, stop). Since qualify_pair rejects any
    missing minutes, no missing candle is silently interpolated.
    """
    if rule not in (*RULES, "NO_TRADE") or (rule != "NO_TRADE" and threshold not in THRESHOLDS):
        raise QualificationError("unknown precommitted candidate")
    pnl = peak = max_drawdown = 0.0
    gross = cost = 0.0
    count = wins = long_count = short_count = 0
    samples = []
    skipped_low_signal = 0
    skipped_overlap = 0
    last_exit = -1
    mid = tuple((b[4] + a[4]) * 0.5 for b, a in zip(bid, ask))
    for i in range(start + plan.lookback, stop - 1 - plan.latency - plan.holding):
        entry_idx = i + 1 + plan.latency
        exit_idx = entry_idx + plan.holding
        if entry_idx <= last_exit:
            skipped_overlap += 1
            continue
        if rule == "NO_TRADE":
            continue
        delta = mid[i] - mid[i - plan.lookback]
        if abs(delta) <= threshold:
            skipped_low_signal += 1
            continue
        direction = 1 if delta > 0 else -1
        if rule == "REVERSAL":
            direction = -direction
        # The observed opening bid/ask already includes the spread.
        entry_quote = ask[entry_idx][1] if direction == 1 else bid[entry_idx][1]
        exit_quote = bid[exit_idx][1] if direction == 1 else ask[exit_idx][1]
        trade_gross = direction * (exit_quote - entry_quote) * plan.quantity
        friction = (2 * plan.slippage_per_side + 2 * plan.commission_per_side) * plan.quantity
        trade_net = trade_gross - friction
        gross += trade_gross
        cost += friction
        pnl += trade_net
        peak = max(peak, pnl)
        max_drawdown = max(max_drawdown, peak - pnl)
        count += 1
        wins += int(trade_net > 0)
        long_count += int(direction == 1)
        short_count += int(direction == -1)
        last_exit = exit_idx
        if len(samples) < 3:
            samples.append({
                "signal_utc": bid[i][0].isoformat(),
                "entry_utc": bid[entry_idx][0].isoformat(),
                "exit_utc": bid[exit_idx][0].isoformat(),
                "side": "LONG" if direction == 1 else "SHORT",
                "net_per_quantity": round(trade_net, 8),
                "execution_basis": "NEXT_OPEN_QUOTE_PROXY_NOT_EXECUTABLE_TICK",
            })
    return {
        "trades": count, "long_trades": long_count, "short_trades": short_count,
        "gross": round(gross, 8), "friction": round(cost, 8),
        "net": round(pnl, 8), "max_drawdown": round(max_drawdown, 8),
        "win_rate": round(wins / count, 6) if count else None,
        "skipped_low_signal": skipped_low_signal,
        "skipped_overlap": skipped_overlap,
        "samples": samples, "inactivity_is_not_profitability": count == 0,
    }


def evaluate_entry_exit_candidates(
    bid_path: str | Path, ask_path: str | Path, *, provenance: dict,
    plan: EntryExitPlan = EntryExitPlan(),
) -> dict:
    """Train-only best candidate versus cash, then frozen diagnostic observation.

    Requires contiguous, structurally consistent M1 files. Does NOT verify the
    provenance claim: metadata supplied by the caller remains untrusted.
    The terminal 20% is intentionally withheld, including from scoring and
    strategy selection. This is NOT an independent sealed exam.
    """
    _check_plan(plan)
    qualified = qualify_pair(bid_path, ask_path, provenance=provenance)
    bid = list(_rows(bid_path))
    ask = list(_rows(ask_path))
    n = len(bid)
    if not 180 <= n <= 200000:
        raise QualificationError("need 180..200000 aligned M1 bars for bounded research")
    train_end = n * 60 // 100
    diagnostic_end = n * 80 // 100
    embargo = plan.lookback + plan.holding + plan.latency + 1
    diagnostic_start = train_end + embargo
    if diagnostic_end - diagnostic_start <= plan.lookback + plan.holding + plan.latency + 3:
        raise QualificationError("not enough disjoint development observations")
    no_trade = _replay(bid, ask, start=0, stop=train_end,
                       plan=plan, rule="NO_TRADE", threshold=0)
    candidates = []
    best = None
    for rule in RULES:
        for threshold in THRESHOLDS:
            metrics = _replay(bid, ask, start=0, stop=train_end,
                              plan=plan, rule=rule, threshold=threshold)
            eligible = metrics["trades"] >= plan.min_training_trades and metrics["net"] > no_trade["net"]
            candidates.append({
                "rule": rule, "threshold": threshold,
                "training": {key: metrics[key] for key in
                             ("trades", "net", "max_drawdown", "friction", "win_rate")},
                "eligible_over_no_trade": eligible,
            })
            if eligible and (best is None or metrics["net"] > best["training"]["net"]):
                best = candidates[-1]
    if best is None:
        selected = {"rule": "NO_TRADE", "threshold": 0.0,
                    "reason": "NO_TRAINING_CANDIDATE_BEAT_CASH_WITH_SUFFICIENT_TRADES"}
    else:
        selected = {"rule": best["rule"], "threshold": best["threshold"],
                    "reason": "POSITIVE_TRAINING_ONLY_NOT_QUALIFIED"}
    rule, threshold = selected["rule"], selected["threshold"]
    dev = _replay(bid, ask, start=diagnostic_start, stop=diagnostic_end,
                  plan=plan, rule=rule, threshold=threshold)
    # No strategy may be promoted on this evidence. In particular, a flat
    # winner scoring zero is an abstention, not positive trading skill.
    report = {
        "schema": "atl_entry_exit_research.v1",
        "data_kind": "STRUCTURALLY_CHECKED_UNATTESTED_BID_ASK",
        "instrument": "XAUUSD", "plan": asdict(plan),
        "precommitted_rules": list(RULES), "precommitted_thresholds": list(THRESHOLDS),
        "provenance_fields_present": qualified["qualified_structure_only"],
        "candles": n, "pair_spread_max": qualified["max_observed_spread"],
        "partitions": {
            "train": [0, train_end], "embargo": [train_end, diagnostic_start],
            "development": [diagnostic_start, diagnostic_end],
            "sealed_terminal_uninspected": [diagnostic_end, n],
        },
        "full_pair_identity_sha256": _hash({
            "bid": [(x[0].isoformat(), *x[1:]) for x in bid],
            "ask": [(x[0].isoformat(), *x[1:]) for x in ask],
        }),
        "no_trade_baseline": {"net": 0.0, "trades": 0, "max_drawdown": 0.0},
        "training_cash_baseline": no_trade,
        "train_candidates": candidates,
        "train_selected": selected,
        "development_selected": dev,
        "development_cash_baseline": {"net": 0.0, "trades": 0},
        "train_only_selection": True,
        "development_did_not_select_weights": True,
        "sealed_terminal_evaluated": False,
        "license_verified": False, "source_independently_attested": False,
        "strategy_qualified": False, "policy_automatically_promoted": False,
        "paper_trading_enabled": False, "live_trading_enabled": False,
        "warning": "Candles and metadata do not prove provider rights, executable ticks, alpha, or trading authorisation.",
    }
    report["report_sha256"] = _hash(report)
    return report
