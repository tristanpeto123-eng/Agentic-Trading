"""Historical XAU/USD BID/ASK research replay for the Evolution Tower.

Only completed, chronological read-only provider quotations are accepted.
This is an approximate, costed simulation, NOT actual CFD executions or
independent evidence of a tradable edge. No broker/order clients here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validated_research_snapshot(snapshot: dict) -> dict:
    """Freeze B/C chronologically and omit final D observations entirely.

    Provider snapshots must originate in trusted server-side OANDA or Dukascopy
    adapters, NEVER from an unauthenticated client payload.
    """
    from agentic_trading.evolution_tower import TowerError
    if not isinstance(snapshot, dict) or snapshot.get("market") != "XAUUSD" or snapshot.get("price_basis") != "bid_ask":
        raise TowerError("Real research requires paired XAUUSD BID/ASK M15 quotes")
    provider = snapshot.get("provider", "")
    if not (provider.startswith("OANDA v20 practice") or provider.startswith("Dukascopy M1 BID/ASK")):
        raise TowerError("Unrecognised server-side XAUUSD quote provider")
    bars = snapshot.get("bars")
    if not isinstance(bars, list) or not 640 <= len(bars) <= 2016:
        raise TowerError("Real research requires 640–2016 completed M15 observations")
    if snapshot.get("source_sha256") != _digest(bars):
        raise TowerError("Real quote source hash mismatch")
    previous = None
    gaps = 0
    for bar in bars:
        try:
            instant = datetime.fromisoformat(bar["open_time"].replace("Z", "+00:00"))
            available = datetime.fromisoformat(bar["available_at"].replace("Z", "+00:00"))
            if instant.utcoffset() != timedelta(0) or available != instant + timedelta(minutes=15):
                raise ValueError("invalid timestamp")
            if available > datetime.now(timezone.utc):
                raise ValueError("uncompleted quote")
            if previous is not None:
                if instant <= previous:
                    raise ValueError("nonmonotonic quote")
                if instant - previous != timedelta(minutes=15):
                    gaps += 1
            previous = instant
            for side in ("bid", "ask"):
                prices = [float(bar[side][k]) for k in ("open", "high", "low", "close")]
                if not all(math.isfinite(x) and 200 <= x <= 20000 for x in prices):
                    raise ValueError("invalid quote value")
                op, high, low, close = prices
                if high < max(op, low, close) or low > min(op, high, close):
                    raise ValueError("invalid quote OHLC")
            for k in ("open", "close"):
                if float(bar["bid"][k]) > float(bar["ask"][k]):
                    raise ValueError("crossed quote")
        except (KeyError, TypeError, AttributeError, OverflowError, ValueError) as exc:
            raise TowerError(f"Real BID/ASK history invalid: {exc}") from exc
    if gaps != snapshot.get("gap_count"):
        raise TowerError("Historical gap-count integrity mismatch")
    n = len(bars)
    b_end = n * 70 // 100
    c_end = n * 90 // 100
    if b_end < 128 or c_end-b_end < 128 or n-c_end < 50:
        raise TowerError("Insufficient chronological B/C/D partition lengths")
    working = bars[:c_end]  # D is excluded from persistent state AND evaluation.
    return {
        "market": "XAUUSD",
        "provider": provider,
        "source_sha256": snapshot["source_sha256"],
        "working_sha256": _digest(working),
        "price_basis": "observed_bid_ask",
        "gap_count": gaps,
        "observations_received": n,
        "b_end": b_end,
        "c_end": c_end,
        "d_bars_withheld": n-c_end,
        "first_open_time": bars[0]["open_time"],
        "last_research_open_time": working[-1]["open_time"],
        "bars": working,
    }


def replay_bidask(genes: list[float], bars: list[dict]) -> dict:
    """Signal at completed bar i; fill at bar i+1 OPEN, using quote sides.

    Costs: observed BID/ASK plus explicitly assumed 3bps adverse slippage,
    2bps commission per side and 0.8bps/rollover funding. Not fill evidence.
    """
    from agentic_trading.evolution_tower import (
        TowerError, _brain, START_EQUITY, MAX_DRAWDOWN, MAX_LEVERAGE,
        SLIPPAGE_BPS, COMMISSION_BPS, OVERNIGHT_BPS,
    )
    if len(bars) < 128:
        raise TowerError("Insufficient real replay bars")
    mids = [(float(x["bid"]["close"])+float(x["ask"]["close"]))/2 for x in bars]
    cash, equity, peak = START_EQUITY, START_EQUITY, START_EQUITY
    pos = 0.0
    max_dd = 0.0
    trades, closed, wins = 0, 0, 0
    cost_total = 0.0
    prev_trade_value = START_EQUITY
    downside = []
    ended, reason = False, None
    previous_held_date = None
    for i in range(24, len(bars)-1):
        current = mids[i]
        history = [(mids[k]/mids[k-1]-1)*100 for k in range(i-9,i+1)]
        mean = sum(history)/len(history)
        volatility = math.sqrt(sum((r-mean)**2 for r in history)/len(history))
        features = [
            max(-1., min(1., (current/mids[i-1]-1)*100)),
            max(-1., min(1., (current/mids[i-5]-1)*100)),
            max(0., min(1., volatility)),
            1. if pos > 0 else -1. if pos < 0 else 0.,
            max(-1., min(1., (equity/START_EQUITY-1)*2)),
            ((i%96)/96)-.5,
        ]
        action = _brain(genes, features)
        desired_sign = (1 if action==1 else -1 if action==2 else
                        0 if action==3 else 1 if pos>0 else -1 if pos<0 else 0)
        current_sign = 1 if pos > 0 else -1 if pos < 0 else 0
        nxt = bars[i+1]
        bid_open, ask_open = float(nxt["bid"]["open"]), float(nxt["ask"]["open"])
        mid_open = (bid_open+ask_open)/2
        mark_bid, mark_ask = float(nxt["bid"]["close"]), float(nxt["ask"]["close"])
        mark_mid = (mark_bid+mark_ask)/2
        # Executions are hypothetical on next OPEN; spread comes from actual sides.
        if desired_sign != current_sign:
            if pos:
                raw_exit = bid_open if pos>0 else ask_open
                exit_price = raw_exit*(1-math.copysign(SLIPPAGE_BPS/10000,pos))
                cash += pos*exit_price
                fee = abs(pos*exit_price)*COMMISSION_BPS/10000
                cash -= fee
                cost_total += fee + abs(pos)*abs(mid_open-exit_price)
                closed += 1
                if cash > prev_trade_value:
                    wins += 1
                prev_trade_value = cash
                pos = 0.
            if desired_sign:
                qty = max(0., min(MAX_LEVERAGE*max(cash, 0)/mid_open,
                                   MAX_LEVERAGE*START_EQUITY/mid_open))
                raw_entry = ask_open if desired_sign>0 else bid_open
                entry_price = raw_entry*(1+desired_sign*SLIPPAGE_BPS/10000)
                pos = desired_sign*qty
                cash -= pos*entry_price
                fee = abs(pos*entry_price)*COMMISSION_BPS/10000
                cash -= fee
                cost_total += fee + qty*abs(entry_price-mid_open)
                trades += 1
        # Explicitly approximate financing; not a sourced broker rollover schedule.
        trading_date = nxt["open_time"][:10]
        if pos and previous_held_date is not None and trading_date != previous_held_date:
            fee = abs(pos*mid_open)*OVERNIGHT_BPS/10000
            cash -= fee
            cost_total += fee
        previous_held_date = trading_date
        previous_equity = equity
        equity = cash + pos*mark_mid
        if not math.isfinite(equity):
            raise TowerError("Nonfinite historical research equity")
        step = equity/previous_equity-1 if previous_equity>0 else -1.
        if step<0:
            downside.append(step*step)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak)
        if equity<=START_EQUITY*(1-MAX_DRAWDOWN) or equity<=0:
            ended, reason = True, "RISK_LIMIT_OR_MARGIN"
            break
    if pos and not ended:
        last = bars[-1]
        raw_exit = float(last["bid"]["close"] if pos>0 else last["ask"]["close"])
        price = raw_exit*(1-math.copysign(SLIPPAGE_BPS/10000, pos))
        cash += pos*price
        fee = abs(pos*price)*COMMISSION_BPS/10000
        cash -= fee
        cost_total += fee + abs(pos)*abs(mids[-1]-price)
        closed += 1
        if cash > prev_trade_value:
            wins += 1
        equity = cash
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak)
    ret = equity/START_EQUITY-1
    downside_dev = math.sqrt(sum(downside)/max(1,len(downside)))
    sortino = max(-10.,min(10.,ret/max(0.001,downside_dev*math.sqrt(len(bars)))))
    fitness = max(-100.,min(100.,ret*100-2.5*max_dd*100+.1*sortino-.025*trades))
    return {
        "equity": round(equity,4), "return_pct": round(ret*100,4),
        "drawdown_pct": round(max_dd*100,4), "trades": trades,
        "closed_trades": closed, "wins": wins,
        "win_rate_pct": round(100*wins/closed,2) if closed else 0.,
        "cost_usd": round(cost_total,4), "sortino_proxy": round(sortino,4),
        "fitness": round(fitness,4), "risk_breached": ended, "death_reason": reason,
    }
