"""Research-only, conservative next-open bid/ask replay.

No broker connectivity, no synthetic claims of live profitability.
"""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path
from .pair_qualification import qualify_pair, _rows
from .data_qualification import QualificationError


@dataclass(frozen=True)
class Trade:
    entry_utc: str
    exit_utc: str
    side: int
    entry: float
    exit: float
    net: float


def replay_signals(bid_path: str | Path, ask_path: str | Path, signals: list[int],
                   *, provenance: dict, fee_per_round_trip: float = 0.0,
                   slippage_per_side: float = 0.0) -> dict:
    """Execute signals on NEXT candle open, close on following candle open.

    signals[i] in {-1,0,1} is decided at close of candle i.
    Assumes no leverage, one unit per trade, no overnight fees.
    No lookahead: a signal on i cannot fill before i+1.
    """
    if fee_per_round_trip < 0 or slippage_per_side < 0:
        raise QualificationError("negative execution costs")
    qualified = qualify_pair(bid_path, ask_path, provenance=provenance)
    bid = list(_rows(bid_path))
    ask = list(_rows(ask_path))
    if len(signals) != len(bid):
        raise QualificationError("signal count must match candle count")
    if any(type(s) is not int or s not in (-1, 0, 1) for s in signals):
        raise QualificationError("signals must be -1, 0 or 1")
    trades = []
    # Require two future opens: fill at i+1, exit at i+2.
    for i in range(len(signals) - 2):
        side = signals[i]
        if side == 0:
            continue
        entry = ask[i+1][1] + slippage_per_side if side == 1 else bid[i+1][1] - slippage_per_side
        exit_ = bid[i+2][1] - slippage_per_side if side == 1 else ask[i+2][1] + slippage_per_side
        net = side * (exit_ - entry) - fee_per_round_trip
        trades.append(Trade(bid[i+1][0].isoformat(), bid[i+2][0].isoformat(),
                            side, entry, exit_, net))
    equity = peak = max_drawdown = 0.0
    for trade in trades:
        equity += trade.net
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak-equity)
    return {"trades": len(trades), "net_per_unit": equity,
            "max_drawdown_per_unit": max_drawdown,
            "win_rate": sum(t.net > 0 for t in trades) / len(trades) if trades else None,
            "trade_records": [t.__dict__ for t in trades],
            "qualified_structure_only": qualified["qualified_structure_only"],
            "license_verified": False, "execution_authorized": False}
