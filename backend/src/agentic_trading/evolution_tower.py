"""Bounded synthetic-only evolutionary research tower.

The browser is a visualization. This CPU-only module is the authoritative
deterministic simulator and neural-weight mutation engine. No broker imports.
A/B/C/D real-data gates are NOT claimed: this prototype only generates
separate toy B and C random-walk tapes. D is never generated or inspected.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import random
from typing import Any

POPULATION = 16
GENERATION_LIMIT = 100
GENES = 6 * 8 + 8 + 8 * 4 + 4
START_EQUITY = 1000.0
MAX_DRAWDOWN = 0.20
MAX_LEVERAGE = 0.5
SPREAD_BPS = 12.0
SLIPPAGE_BPS = 3.0
COMMISSION_BPS = 2.0
OVERNIGHT_BPS = 0.8


class TowerError(ValueError):
    pass


def _digest(payload: Any) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def make_tape(seed: int, count: int) -> list[float]:
    """A seeded, toy closed-price series, never externally sourced CFD data."""
    if count < 128 or count > 768:
        raise TowerError("Invalid bounded synthetic tape length")
    rng = random.Random(seed)
    price = 100.0
    tape = [price]
    for _ in range(count):
        price *= math.exp(rng.gauss(0, .0025))
        tape.append(price)
    return tape


def _brain(genes: list[float], features: list[float]) -> int:
    """Small fixed 6->8->4 MLP, including a distinct CLOSE action."""
    if len(genes) != GENES or any(not math.isfinite(v) or abs(v) > 6 for v in genes):
        raise TowerError("Neural chromosome invalid")
    hidden = []
    for j in range(8):
        value = genes[48+j]
        for i in range(6):
            value += features[i] * genes[i*8+j]
        hidden.append(math.tanh(value))
    output = []
    for k in range(4):
        value = genes[88+k]
        for j in range(8):
            value += hidden[j] * genes[56+j*4+k]
        output.append(value)
    return max(range(4), key=lambda k: output[k])


def evaluate(genes: list[float], tape: list[float]) -> dict:
    """Costed pathwise simulation with an independent, immutable risk ceiling.

    Signals on t are executed at the NEXT closed-price observation with
    adverse bid/ask, commission and slippage. This is *not* a CFD fill model.
    """
    if len(tape) < 128 or any(x <= 0 or not math.isfinite(x) for x in tape):
        raise TowerError("Invalid toy market tape")
    cash = START_EQUITY
    pos = 0.0
    equity = START_EQUITY
    peak = equity
    max_dd = 0.0
    trades = 0
    wins = 0
    closed = 0
    cost_total = 0.0
    prev_trade_value = START_EQUITY
    downside = []
    ended = False
    reason = None
    held_bars = 0
    for i in range(24, len(tape)-1):
        current = tape[i]
        next_price = tape[i+1]
        r1 = (tape[i] / tape[i-1] - 1)*100
        r5 = (tape[i] / tape[i-5] - 1)*100
        previous = [(tape[k]/tape[k-1]-1)*100 for k in range(i-9,i+1)]
        volatility = math.sqrt(sum((r - sum(previous)/len(previous))**2 for r in previous)/len(previous))
        features = [
            max(-1., min(1., r1)), max(-1., min(1., r5)),
            max(0., min(1., volatility)), pos and math.copysign(1, pos) or 0.,
            max(-1., min(1., (equity / START_EQUITY-1)*2)),
            ((i % 96)/96)-.5,
        ]
        action = _brain(genes, features)
        desired_sign = (1 if action == 1 else -1 if action == 2 else
                        0 if action == 3 else (1 if pos>0 else -1 if pos<0 else 0))
        current_sign = 1 if pos>0 else -1 if pos<0 else 0
        # Do not allow a learner to change leverage, maintenance or drawdown.
        if desired_sign != current_sign:
            if pos:
                # Exit at next observation's adverse side, not the current bar.
                exit_price = next_price*(1 - math.copysign((SPREAD_BPS/2+SLIPPAGE_BPS)/10000, pos))
                cash += pos*exit_price
                cost = abs(pos*exit_price)*COMMISSION_BPS/10000
                cash -= cost
                cost_total += cost + abs(pos)*(next_price-exit_price)*current_sign
                closed += 1
                if cash > prev_trade_value:
                    wins += 1
                prev_trade_value = cash
                pos = 0.
            if desired_sign:
                qty = max(0., min(MAX_LEVERAGE*cash / next_price, MAX_LEVERAGE*START_EQUITY/next_price))
                entry_price = next_price*(1 + desired_sign*(SPREAD_BPS/2+SLIPPAGE_BPS)/10000)
                pos = desired_sign*qty
                cash -= pos*entry_price
                cost = abs(pos*entry_price)*COMMISSION_BPS/10000
                cash -= cost
                cost_total += cost + qty*abs(entry_price-next_price)
                trades += 1
        elif pos:
            held_bars += 1
        if pos and (i+1) % 96 == 0:
            swap = abs(pos*next_price)*OVERNIGHT_BPS/10000
            cash -= swap
            cost_total += swap
        previous_equity = equity
        equity = cash + pos*next_price
        if not math.isfinite(equity):
            raise TowerError("Nonfinite simulated equity")
        step_return = equity/previous_equity-1 if previous_equity>0 else -1
        if step_return < 0:
            downside.append(step_return*step_return)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak)
        if equity <= START_EQUITY*(1-MAX_DRAWDOWN) or equity <= 0:
            ended = True
            reason = "RISK_LIMIT_OR_MARGIN"
            break
    if pos and not ended:
        # Forced close and adverse close-out friction at end of tape.
        close_price = tape[-1]*(1-math.copysign((SPREAD_BPS/2+SLIPPAGE_BPS)/10000,pos))
        cash += pos*close_price
        fee = abs(pos*close_price)*COMMISSION_BPS/10000
        cash -= fee
        cost_total += fee + abs(pos)*abs(tape[-1]-close_price)
        closed += 1
        if cash > prev_trade_value:
            wins += 1
        equity = cash
        peak = max(peak,equity)
        max_dd = max(max_dd,(peak-equity)/peak)
    ret = equity/START_EQUITY-1
    downside_deviation = math.sqrt(sum(downside)/max(1,len(downside)))
    # Reject excessive gambling. Sortino-style score remains finite and bounded.
    sortino = max(-10.,min(10.,ret/max(0.001,downside_deviation*math.sqrt(len(tape)))))
    fitness = max(-100., min(100.,ret*100 - 2.5*max_dd*100 + .1*sortino - .025*trades))
    return {
        "equity": round(equity, 4), "return_pct": round(ret*100, 4),
        "drawdown_pct": round(max_dd*100, 4), "trades": trades,
        "closed_trades": closed, "wins": wins,
        "win_rate_pct": round(100*wins/closed, 2) if closed else 0.,
        "cost_usd": round(cost_total, 4), "sortino_proxy": round(sortino, 4),
        "fitness": round(fitness, 4), "risk_breached": ended,
        "death_reason": reason,
    }


def _new_genes(rng: random.Random) -> list[float]:
    return [round(rng.gauss(0,0.28),8) for _ in range(GENES)]


def _floor(result: dict, rank: int) -> int:
    # This is a synthetic research visual rank, never independent evidence.
    if result["risk_breached"]:
        return 0
    if (result["return_pct"] <= 0 or result["drawdown_pct"] > 12
            or result["closed_trades"] < 8 or result["fitness"] <= 0):
        return max(1, 2 + (POPULATION-rank)*1)
    return min(49, 21 + (POPULATION-rank)*2)


def _grade(genes: list[float], generation: int) -> dict:
    # Separate deterministic toy B and C tapes. The final D tape is never generated.
    b_seed = 340003 + generation*101
    c_seed = 730009 + generation*103
    b_tape=make_tape(b_seed, 384)
    c_tape=make_tape(c_seed, 192)
    b=evaluate(genes,b_tape)
    c=evaluate(genes,c_tape)
    return {"training":b,"selection":c,"source_kind":"SYNTHETIC_RANDOM_WALK_ONLY",
            "slice_b_sha256": _digest(b_tape), "slice_c_sha256":_digest(c_tape)}


def initial_state(seed: int=20261101, count: int=POPULATION) -> dict:
    if not 10<=count<=20:
        raise TowerError("Population must start with 10–20 agents")
    rng=random.Random(seed)
    agents=[]
    for i in range(count):
        genes=_new_genes(rng)
        agents.append({"id":f"ATL-G0-{i+1:03d}","generation":0,"parent_id":None,
                       "genes":genes,"genome_sha256":_digest(genes),"status":"nursery",
                       "floor":1,"metrics":None})
    return {"schema":"atl_evolution_tower.v1","seed":seed,"generation":0,
            "population":agents,"total_born":count,"total_culled":0,
            "mode":"SYNTHETIC_ONLY","independent_exam":False,
            "paper_trading_enabled":False,"live_trading_enabled":False}


def advance_state(state: dict) -> tuple[dict,list[dict]]:
    if state.get("schema")!="atl_evolution_tower.v1":
        raise TowerError("Unknown evolution tower schema")
    if state["generation"]>=GENERATION_LIMIT:
        raise TowerError("Generation safety limit reached")
    gen=state["generation"]+1
    ranked=[]
    for item in state["population"]:
        genes=item["genes"]
        if _digest(genes)!=item["genome_sha256"]:
            raise TowerError("Research chromosome integrity mismatch")
        outcome=_grade(genes,gen)
        ranked.append({**item,"metrics":outcome})
    ranked.sort(key=lambda a:(a["metrics"]["selection"]["risk_breached"],
                              -a["metrics"]["selection"]["fitness"],a["id"]))
    # Keep up to half; evict risk failures as well. Never elect a real champion.
    keep_count=len(ranked)//2
    kept=[]
    removed=[]
    for i,item in enumerate(ranked):
        result=item["metrics"]["selection"]
        if i>=keep_count or result["risk_breached"]:
            removed.append({**item,"floor":0,"status":"archived",
                            "reason":result["death_reason"] or "SELECTION"})
        else:
            kept.append({**item,"floor":_floor(result,i),
                         "status":"research_leader" if i==0 else "competing"})
    rng=random.Random(state["seed"]+gen*10007)
    parents=kept or ranked[:2]
    births=[]
    for slot in range(len(ranked)-len(kept)):
        parent=parents[slot%len(parents)]
        mutated=[round(max(-3,min(3,g+rng.gauss(0,0.06))),8) for g in parent["genes"]]
        child={"id":f"ATL-G{gen}-{slot+1:03d}","generation":gen,
               "parent_id":parent["id"],"genes":mutated,
               "genome_sha256":_digest(mutated),"floor":1,
               "status":"nursery","metrics":None}
        births.append(child)
    next_state={**state,"generation":gen,"population":kept+births,
                "total_born":state["total_born"]+len(births),
                "total_culled":state["total_culled"]+len(removed)}
    events=[{"type":"GENERATION_EVALUATED","generation":gen,"kept_ids":[x["id"] for x in kept],
             "removed":[{"id":r["id"],"from_floor":r["floor"],"reason":r["reason"],
                         "selection":r["metrics"]["selection"]} for r in removed],
             "born":[{"id":b["id"],"parent_id":b["parent_id"]} for b in births],
             "source_kind":"SYNTHETIC_RANDOM_WALK_ONLY",
             "selection_is_not_validation":True}]
    return next_state,events


def public_state(state: dict, events: list[dict]|None=None) -> dict:
    """Never expose strategy chromosomes or any qualification claim to browser."""
    return {
        **{k:v for k,v in state.items() if k!="population"},
        "agents":[{k:v for k,v in agent.items() if k!="genes"}
                  for agent in state["population"]],
        "last_events":events or [],
        "champions":[],"penthouse_locked":True,"qualification":"unqualified",
        "baseline":"FLAT_ZERO_TRADE","performance_kind":"TOY_SYNTHETIC_ONLY",
        "worker_mode":"MANUAL_OR_BROWSER_OPEN","final_slice_d_accessed":False,
        "note":"Research demonstration on deterministic synthetic random walks. Floor reflects relative toy-simulation fitness, not a market edge. No broker, independent alpha or background VPS worker.",
    }
