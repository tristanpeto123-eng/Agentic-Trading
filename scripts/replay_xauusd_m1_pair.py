#!/usr/bin/env python3
"""Offline point-in-time XAUUSD M1 BID/ASK *indicative* cost replay.

Uses already-completed candles for a fixed demonstration signal, executes
hypothetically at subsequent BID/ASK candle opening proxies, and models
additional assumed costs. No tick fills, model training, holdout qualification,
data rights, broker access, or trading authority are implied.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path

from audit_xauusd_m1_pair import _read_quotes, audit_bid_ask, QuoteAuditError

MINUTE = timedelta(minutes=1)
MAX_EXAMPLES = 12


class ReplayError(ValueError):
    """Unsafe replay configuration or inconsistent quote pairing."""


def _decimal(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise argparse.ArgumentTypeError("Expected finite decimal") from exc
    if not number.is_finite():
        raise argparse.ArgumentTypeError("Expected finite decimal")
    return number


def _validate(lookback: int, holding: int, latency: int,
              threshold: Decimal, quantity: Decimal,
              commission: Decimal, slippage: Decimal) -> None:
    for value, low, high, name in (
        (lookback, 2, 120, "lookback"),
        (holding, 1, 120, "holding"),
        (latency, 1, 30, "latency"),
    ):
        if type(value) is not int or not low <= value <= high:
            raise ReplayError(f"{name} outside bounded replay limits")
    for value, name in (
        (threshold, "signal threshold"),
        (quantity, "quantity"),
        (commission, "commission"),
        (slippage, "slippage"),
    ):
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ReplayError(f"{name} must be a finite Decimal")
    if threshold < 0 or not Decimal("0") < quantity <= Decimal("1"):
        raise ReplayError("threshold or quantity outside bounded replay limits")
    if commission < 0 or slippage < 0:
        raise ReplayError("assumed commission and slippage cannot be negative")


def replay_bid_ask(
    bid_path: Path, ask_path: Path, *, lookback: int = 5,
    holding: int = 5, latency: int = 1,
    threshold: Decimal = Decimal("0.75"),
    quantity: Decimal = Decimal("0.10"),
    commission: Decimal = Decimal("0.05"),
    slippage: Decimal = Decimal("0.20"),
) -> dict:
    """Replay a fixed, untrained momentum illustration without overlap.

    A signal uses midpoint closes through the completed signal candle i.
    After its close (i+1 minute) and at least one FULL latency minute,
    the illustrative entry is at aligned bar i+1+latency's OPEN. Exits
    at the OPEN of a later aligned bar. Longs cross ASK in/BID out, shorts
    BID in/ASK out. Spread is ALREADY embedded in those side prices;
    only extra commission/slippage are subtracted, avoiding double-counting.
    An OHLC bar open is NOT a simultaneous broker tick or guaranteed fill.
    """
    _validate(lookback, holding, latency, threshold, quantity, commission, slippage)
    audit = audit_bid_ask(bid_path, ask_path)
    _, bids = _read_quotes(bid_path)
    _, asks = _read_quotes(ask_path)
    common = sorted(bids.keys() & asks.keys())

    # Reject invalid open-side quotes rather than benefitting from crossed prices.
    for stamp in common:
        if asks[stamp][0] <= bids[stamp][0]:
            raise ReplayError(f"Non-positive BID/ASK opening spread at {stamp.isoformat()}")

    equity = Decimal("0")
    peak = Decimal("0")
    max_drawdown = Decimal("0")
    wins = losses = flats = 0
    gross_total = friction_total = Decimal("0")
    examples: list[dict] = []
    last_exit = None
    skipped_gaps = skipped_flat = skipped_overlap = 0
    total_trades = 0

    for i in range(lookback, len(common) - (1 + latency + holding)):
        entry_idx = i + 1 + latency
        exit_idx = entry_idx + holding
        entry_time, exit_time = common[entry_idx], common[exit_idx]

        if last_exit is not None and entry_time <= last_exit:
            skipped_overlap += 1
            continue
        # Require all lookback, signal, entry, hold and exit bars contiguous.
        # Missing quotes are never interpolated, including session boundaries.
        if any(common[k] - common[k - 1] != MINUTE
               for k in range(i - lookback + 1, exit_idx + 1)):
            skipped_gaps += 1
            continue

        def midpoint_close(index: int) -> Decimal:
            time = common[index]
            return (bids[time][3] + asks[time][3]) / 2

        delta = midpoint_close(i) - midpoint_close(i - lookback)
        if abs(delta) <= threshold:
            skipped_flat += 1
            continue
        direction = "LONG" if delta > 0 else "SHORT"
        if direction == "LONG":
            entry_px = asks[entry_time][0]
            exit_px = bids[exit_time][0]
            gross = (exit_px - entry_px) * quantity
        else:
            entry_px = bids[entry_time][0]
            exit_px = asks[exit_time][0]
            gross = (entry_px - exit_px) * quantity

        # Two-sided cost beyond the observed side-quote spread.
        additional_cost = quantity * 2 * (commission + slippage)
        net = gross - additional_cost
        gross_total += gross
        friction_total += additional_cost
        equity += net
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        wins += int(net > 0)
        losses += int(net < 0)
        flats += int(net == 0)
        total_trades += 1
        last_exit = exit_time

        if len(examples) < MAX_EXAMPLES:
            examples.append({
                "signal_known_at_utc": (common[i] + MINUTE).isoformat(),
                "entry_open_utc": entry_time.isoformat(),
                "exit_open_utc": exit_time.isoformat(),
                "direction": direction,
                "entry_quote_proxy_usd_per_oz": str(entry_px),
                "exit_quote_proxy_usd_per_oz": str(exit_px),
                "hypothetical_gross_usd": str(gross),
                "additional_assumed_cost_usd": str(additional_cost),
                "hypothetical_net_usd": str(net),
            })

    return {
        "schema": "xauusd_m1_quote_side_replay.v1",
        "research_only": True,
        "audited_source_hashes": {
            "bid_sha256": audit["bid"]["file_sha256"],
            "ask_sha256": audit["ask"]["file_sha256"],
        },
        "matched_m1_bars": audit["aligned_m1_rows"],
        "fixed_signal": "midpoint CLOSE momentum over completed lookback bars; no fitting",
        "assumptions": {
            "lookback_m1": lookback,
            "holding_m1": holding,
            "additional_latency_full_minutes": latency,
            "minimum_signal_delta_usd_per_oz": str(threshold),
            "quantity_oz": str(quantity),
            "commission_usd_per_oz_per_side": str(commission),
            "slippage_usd_per_oz_per_side": str(slippage),
            "entry_exit": "subsequent BID/ASK candle OPEN proxies (not executable tick quotes)",
            "spread": "included by crossing ASK/BID or BID/ASK; not double-charged",
        },
        "outcomes": {
            "closed_hypothetical_trades": total_trades,
            "positive_net": wins,
            "negative_net": losses,
            "flat_net": flats,
            "win_rate_pct": str((Decimal(wins) * 100 / total_trades).quantize(
                Decimal("0.01"))) if total_trades else None,
            "gross_usd": str(gross_total),
            "additional_assumed_cost_usd": str(friction_total),
            "hypothetical_net_usd": str(equity),
            "peak_to_trough_drawdown_usd": str(max_drawdown),
        },
        "skips": {
            "noncontiguous_quotes": skipped_gaps,
            "no_signal": skipped_flat,
            "overlapping_position": skipped_overlap,
        },
        "first_trade_examples": examples,
        "independent_provenance_and_licence_verified": False,
        "independent_holdout_or_model_qualification": False,
        "actual_fills_or_realised_profitability_proven": False,
        "broker_execution_enabled": False,
        "paper_trading_eligible": False,
        "live_trading_eligible": False,
        "disclaimer": (
            "Illustrative after-assumed-cost quote-side markouts only. A minute OHLC "
            "OPEN is not a simultaneous tradable tick, so real fills, latency, "
            "funding, impact, stops and market access are unverified. "
            "No sealed out-of-sample test or source rights have been validated."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bid_csv", type=Path)
    p.add_argument("ask_csv", type=Path)
    p.add_argument("--lookback", type=int, default=5)
    p.add_argument("--holding", type=int, default=5)
    p.add_argument("--latency", type=int, default=1)
    p.add_argument("--threshold", type=_decimal, default=Decimal("0.75"))
    p.add_argument("--quantity", type=_decimal, default=Decimal("0.10"))
    p.add_argument("--commission", type=_decimal, default=Decimal("0.05"))
    p.add_argument("--slippage", type=_decimal, default=Decimal("0.20"))
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        report = replay_bid_ask(
            args.bid_csv, args.ask_csv,
            lookback=args.lookback, holding=args.holding, latency=args.latency,
            threshold=args.threshold, quantity=args.quantity,
            commission=args.commission, slippage=args.slippage,
        )
    except (ReplayError, QuoteAuditError, OSError) as exc:
        p.exit(2, f"Offline replay rejected: {exc}\n")
    result = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
