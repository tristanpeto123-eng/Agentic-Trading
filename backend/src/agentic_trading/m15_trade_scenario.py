"""Quarantined XAUUSD M15 after-cost *scenario* lab; no execution inference.

Historical M15 OHLC is insufficient to certify real bid/ask fills, spread,
stop order sequencing, market impact or profit. This module deliberately uses
named illustrative assumptions, never writes trade_experiences, never reads the
final holdout and never grants trading rights. Fixed skill rules remain frozen.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Sequence

from agentic_trading.candle_study import (
    TACTICS, LOOKBACK, BATCH_SIZE, UPDATE_EVERY, _forecast, CandleStudyError
)
from agentic_trading.chronological_holdout import split_chronological
from agentic_trading.data_engine import Candle, STEP

ZERO = Decimal("0")
DEFAULT_STARTING_EQUITY = Decimal("1000.00")


@dataclass(frozen=True)
class AssumedCosts:
    """Hypothetical USD per troy oz, NOT measured from the source feed."""
    full_spread_usd_per_oz: Decimal = Decimal("0.50")
    slippage_usd_per_oz_per_side: Decimal = Decimal("0.20")
    commission_usd_per_oz_per_side: Decimal = Decimal("0.05")
    quantity_oz: Decimal = Decimal("0.10")

    def __post_init__(self):
        for key in ("full_spread_usd_per_oz", "slippage_usd_per_oz_per_side",
                    "commission_usd_per_oz_per_side", "quantity_oz"):
            number = getattr(self, key)
            if not isinstance(number, Decimal) or not number.is_finite():
                raise CandleStudyError("All assumed cost values must be finite Decimal")
        if (self.full_spread_usd_per_oz <= ZERO or
            self.slippage_usd_per_oz_per_side < ZERO or
            self.commission_usd_per_oz_per_side < ZERO or
            not ZERO < self.quantity_oz <= Decimal("1")):
            raise CandleStudyError("Assumed costs or quantity are outside bounded research limits")

    @property
    def round_trip_cost_per_oz(self) -> Decimal:
        return (self.full_spread_usd_per_oz
                + 2 * self.slippage_usd_per_oz_per_side
                + 2 * self.commission_usd_per_oz_per_side)

    def json(self) -> dict:
        return {key: str(getattr(self, key)) for key in (
            "full_spread_usd_per_oz", "slippage_usd_per_oz_per_side",
            "commission_usd_per_oz_per_side", "quantity_oz"
        )}


def _empty() -> dict:
    return {"closed": 0, "good": 0, "bad": 0, "flat": 0,
            "gross_usd": ZERO, "cost_usd": ZERO, "net_usd": ZERO,
            "gross_wins_usd": ZERO, "gross_losses_usd": ZERO}


def _accumulate(stats: dict, trade: dict) -> None:
    net = trade["net_usd"]
    stats["closed"] += 1
    stats["good"] += int(net > ZERO)
    stats["bad"] += int(net < ZERO)
    stats["flat"] += int(net == ZERO)
    stats["gross_usd"] += trade["gross_usd"]
    stats["cost_usd"] += trade["cost_usd"]
    stats["net_usd"] += net
    stats["gross_wins_usd"] += max(ZERO, net)
    stats["gross_losses_usd"] += max(ZERO, -net)


def _combine(stats: Sequence[dict]) -> dict:
    output = _empty()
    for entry in stats:
        for key in output:
            output[key] += entry[key]
    return output


def _present(stats: dict) -> dict:
    lost = stats["gross_losses_usd"]
    return {
        "closed": stats["closed"], "good": stats["good"],
        "bad": stats["bad"], "flat": stats["flat"],
        "gross_usd": str(stats["gross_usd"]),
        "cost_usd": str(stats["cost_usd"]),
        "net_usd": str(stats["net_usd"]),
        "win_rate_pct": round(100 * stats["good"] / stats["closed"], 2) if stats["closed"] else None,
        "expectancy_usd": str(stats["net_usd"] / stats["closed"]) if stats["closed"] else None,
        "profit_factor": str(stats["gross_wins_usd"] / lost) if lost else None,
    }


def _run_batch(
    bars: Sequence[Candle], start: int, end: int, key: str, costs: AssumedCosts
) -> tuple[dict, list[dict], int]:
    counts = _empty()
    trades: list[dict] = []
    skipped = 0
    for i in range(max(LOOKBACK, start), end - 1):
        # A signal is known only after bar i completes. Entry is *assumed*
        # at next observed M15 open; exit at that completed bar's close.
        # No spread/quote price is inferred from M15 input.
        if any(bars[j].open_time - bars[j - 1].open_time != STEP
               for j in range(i - LOOKBACK + 1, i + 2)):
            skipped += 1
            continue
        direction = _forecast(bars, i, key)
        if not direction:
            skipped += 1
            continue
        following = bars[i + 1]
        observed = Decimal(following.close) - Decimal(following.open)
        gross = direction * observed * costs.quantity_oz
        friction = costs.round_trip_cost_per_oz * costs.quantity_oz
        net = gross - friction
        trade = {
            "signal_at": bars[i].available_at.isoformat(),
            "entry_at": following.open_time.isoformat(),
            "exit_at": following.available_at.isoformat(),
            "direction": "LONG" if direction > 0 else "SHORT",
            "rule": key,
            "entry_reference": following.open,
            "exit_reference": following.close,
            "gross_usd": gross,
            "cost_usd": friction,
            "net_usd": net,
            "outcome": "good" if net > ZERO else "bad" if net < ZERO else "flat",
        }
        _accumulate(counts, trade)
        trades.append(trade)
    return counts, trades, skipped


def study_costed_outcomes(
    candles: Sequence[Candle], *,
    dataset_id: str,
    source_sha256: str,
    allowed_tactics: tuple[str, ...] = TACTICS,
    batch_size: int = BATCH_SIZE,
    embargo_bars: int = 96,
    assumptions: AssumedCosts = AssumedCosts(),
) -> dict:
    """Training-only adaptive selector, frozen development validation, sealed test.

    The entire training period is used to assess fixed-rule alternatives after
    each completed five-batch window; only the selector gets updated.
    The assumed-fill outcomes are ephemeral, cannot enter trusted closed-trade
    memory or neural checkpoints and do not validate real-market profitability.
    """
    if not dataset_id or len(source_sha256) != 64 or any(
        ch not in "0123456789abcdef" for ch in source_sha256.lower()
    ):
        raise CandleStudyError("Frozen source metadata missing or invalid")
    tactics = tuple(key for key in TACTICS if key in allowed_tactics)
    if not tactics:
        raise CandleStudyError("Student has no supported hypothetical trade tactics")
    if not 24 <= batch_size <= 512 or embargo_bars < LOOKBACK + 1:
        raise CandleStudyError("Invalid batch size or embargo")
    try:
        split = split_chronological(candles, embargo_bars=embargo_bars, minimum_per_fold=100)
    except (ValueError, AttributeError, TypeError) as exc:
        raise CandleStudyError(f"Dataset partition refused: {exc}") from exc
    train, development = split.train, split.validation
    selected, selector_version = tactics[0], 1
    batches: list[dict] = []
    recent_candidates: list[dict[str, dict]] = []
    cumulative = _empty()
    equity = DEFAULT_STARTING_EQUITY
    peak = equity
    max_drawdown = ZERO
    sampled_trades: list[dict] = []
    for start in range(0, len(train), batch_size):
        end = min(start + batch_size, len(train))
        candidate = {}
        trace = {}
        skipped = 0
        for tactic in tactics:
            counts, trades, n_skipped = _run_batch(train, start, end, tactic, assumptions)
            candidate[tactic], trace[tactic] = counts, trades
            if tactic == selected:
                skipped = n_skipped
        scored = candidate[selected]
        for trade in trace[selected]:
            equity += trade["net_usd"]
            peak = max(peak, equity)
            if peak > ZERO:
                max_drawdown = max(max_drawdown, (peak - equity) / peak)
        cumulative = _combine((cumulative, scored))
        sampled_trades.extend(trace[selected][-2:])
        point = {
            "batch": len(batches) + 1,
            "end_at": train[end - 1].available_at.isoformat(),
            "selected_rule": selected,
            "selector_version": selector_version,
            "closed": scored["closed"],
            "good": scored["good"],
            "bad": scored["bad"],
            "net_usd": str(scored["net_usd"]),
            "cumulative_net_usd": str(cumulative["net_usd"]),
            "hypothetical_equity_usd": str(equity),
            "skipped": skipped,
            "selector_updated_after": False,
        }
        recent_candidates.append(candidate)
        if point["batch"] % UPDATE_EVERY == 0:
            last = recent_candidates[-UPDATE_EVERY:]
            options = {k: _combine([row[k] for row in last]) for k in tactics}
            eligible = [k for k in tactics if options[k]["closed"] >= 20]
            if eligible:
                selected = max(eligible, key=lambda k: (
                    options[k]["net_usd"],
                    -options[k]["cost_usd"],
                    -tactics.index(k),
                ))
            selector_version += 1
            point["selector_updated_after"] = True
            point["next_selected_rule"] = selected
            point["next_selector_version"] = selector_version
        batches.append(point)

    validated: list[dict] = []
    for start in range(0, len(development), batch_size):
        end = min(start + batch_size, len(development))
        counts, _, _ = _run_batch(development, start, end, selected, assumptions)
        validated.append(counts)
    validation = _combine(validated)
    config = {
        "dataset_id": dataset_id,
        "source_sha256": source_sha256,
        "split_manifest_sha256": split.manifest_sha256,
        "tactics": tactics,
        "batch_size": batch_size,
        "embargo_bars": embargo_bars,
        "cost_assumptions": assumptions.json(),
    }
    hash_ = sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    preview = [{
        **{k: v for k, v in t.items() if k not in ("gross_usd", "cost_usd", "net_usd")},
        "gross_usd": str(t["gross_usd"]), "cost_usd": str(t["cost_usd"]),
        "net_usd": str(t["net_usd"]),
    } for t in sampled_trades[-30:]]
    return {
        "schema_version": "m15_hypothetical_cost_scenario.v1",
        "mode": "scenario_assumed_m15_next_open_to_close",
        "source_verified": False,
        "price_basis_verified": False,
        "research_eligible": False,
        "trade_execution_performed": False,
        "fill_assumptions_independently_validated": False,
        "neural_training_performed": False,
        "durable_trade_memory_written": False,
        "model_promotion_allowed": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "dataset_id": dataset_id,
        "source_sha256": source_sha256,
        "scenario_sha256": hash_,
        "training_bars": len(train),
        "development_validation_bars": len(development),
        "sealed_holdout_bars": len(split.test),
        "holdout_evaluated": False,
        "selector_version": selector_version,
        "selected_rule": selected,
        "update_every_batches": UPDATE_EVERY,
        "assumed_starting_equity_usd": str(DEFAULT_STARTING_EQUITY),
        "assumed_costs": assumptions.json(),
        "round_trip_cost_usd_per_oz": str(assumptions.round_trip_cost_per_oz),
        "training": _present(cumulative),
        "development_validation": {
            **_present(validation), "selector_frozen": True,
        },
        "training_max_drawdown_fraction": str(max_drawdown),
        "batches": batches,
        "hypothetical_outcome_preview": preview,
        "warning": (
            "SCENARIO ONLY: these are hypothetical M15 next-open-to-close observations "
            "with illustrative fixed spread/slippage/commission assumptions, NOT "
            "observed bid/ask fills, audited financial P&L, a validated trading "
            "strategy, or a neural model. No stops, intrabar path, margin, funding, "
            "liquidation or execution latency are modelled; outcomes may be "
            "unrealistic. The final holdout remains untouched."
        ),
    }
