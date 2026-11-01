"""Bounded evolutionary research tower, with quarantined real BID/ASK replay.

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
PROBATION_ASSESSMENTS = 3  # Three replays; NOT three independent market samples.
MAX_PROBATION_RETIREMENTS = 2  # Normal turnover is gradual, never compulsory.
# Purposeful *research-only* exploration, not a requirement to execute an order.
# New directional candidate weights are evaluated against real costs and risk.
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
    entry_samples = []
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
                if len(entry_samples) < 5:
                    entry_samples.append({"step":i+1,
                                          "side":"BUY" if desired_sign>0 else "SELL",
                                          "price":round(entry_price, 5),
                                          "price_basis":"ASSUMED_SYNTHETIC_EXECUTION"})
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
        "fitness": round(fitness, 4), "entry_samples":entry_samples,
        "risk_breached": ended,
        "death_reason": reason,
    }


def _new_genes(rng: random.Random, *, explore_side: str | None = None) -> list[float]:
    """Seed optional directional RESEARCH candidates, never orders or fills.

    Only new/respawned chromosomes are seeded; existing saved genomes are
    never silently altered. Exploration changes neural output bias, not the
    execution policy, broker state or fixed risk controls.
    """
    genes = [round(rng.gauss(0,0.28),8) for _ in range(GENES)]
    if explore_side in ("BUY","SELL"):
        genes[88] = round(genes[88]-0.65,8)  # lower inactive HOLD preference
        genes[91] = round(genes[91]-0.65,8)  # lower flat CLOSE preference
        genes[89 if explore_side=="BUY" else 90] = round(
            genes[89 if explore_side=="BUY" else 90]+1.5,8)
    return genes


def _floor(result: dict, rank: int) -> int:
    # Relative research-floor rank, never independent validation or permission.
    if result["risk_breached"]:
        return 0
    if (result["return_pct"] <= 0 or result["drawdown_pct"] > 12
            or result["closed_trades"] < 8 or result["fitness"] <= 0):
        return max(1, 2 + (POPULATION-rank)*1)
    return min(49, 21 + (POPULATION-rank)*2)


def _grade(genes: list[float], generation: int, real_data: dict | None = None) -> dict:
    if real_data is not None:
        from agentic_trading.evolution_tower_real import replay_bidask
        rows = real_data["bars"]
        if _digest(rows) != real_data["working_sha256"]:
            raise TowerError("Immutable real quote tape integrity mismatch")
        b_rows = rows[:real_data["b_end"]]
        c_rows = rows[real_data["b_end"]:]
        b, c = replay_bidask(genes, b_rows), replay_bidask(genes, c_rows)
        return {"training": b, "selection": c,
                "source_kind": "REAL_XAUUSD_BID_ASK_RESEARCH_UNQUALIFIED",
                "slice_b_sha256": _digest(b_rows), "slice_c_sha256": _digest(c_rows)}
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
        # Four of every eight recruits explore each direction; the rest
        # remain unbiased. No policy overrides neural decisions at replay.
        side = "BUY" if i%4==0 else "SELL" if i%4==1 else None
        genes=_new_genes(rng, explore_side=side)
        agents.append({"id":f"ATL-G0-{i+1:03d}","generation":0,"parent_id":None,
                       "genes":genes,"genome_sha256":_digest(genes),"status":"nursery",
                       "floor":1,"metrics":None,
                       "assessments":0,"probation_streak":0})
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
        outcome=_grade(genes,gen,state.get("real_data"))
        ranked.append({**item,"metrics":outcome})
    # Real C is diagnostic only; repeated selection on C would contaminate it.
    selection_key = "training" if state.get("real_data") else "selection"
    ranked.sort(key=lambda a:(a["metrics"][selection_key]["risk_breached"],
                              -a["metrics"][selection_key]["fitness"],a["id"]))
    # Survival is determined by absolute outcomes, not percentile ranking.
    # Risk failures exit immediately. Unprofitable/inactive agents receive
    # several assessments on the SAME data (not independent confirmation).
    # Limit non-risk retirements per generation to avoid a mass nursery purge.
    probation_candidates = []
    for item in ranked:
        result = item["metrics"][selection_key]
        weak = (result["trades"] == 0 or result["return_pct"] <= -0.05
                or (result["return_pct"] <= 0 and result["fitness"] < 0))
        streak = (item.get("probation_streak", 0) + 1) if weak else 0
        item["assessments"] = item.get("assessments", 0) + 1
        item["probation_streak"] = streak
        if not result["risk_breached"] and streak >= PROBATION_ASSESSMENTS:
            probation_candidates.append(item)
    # Prioritise chronically inactive bots for vacancy-based exploration.
    # Even an entry-capable loss-maker never gets a free qualification.
    probation_candidates.sort(key=lambda x: (
        x["metrics"][selection_key]["trades"] != 0,
        -x["probation_streak"], x["metrics"][selection_key]["fitness"], x["id"]))
    retiring = {x["id"] for x in probation_candidates[:MAX_PROBATION_RETIREMENTS]}
    kept, removed = [], []
    for i,item in enumerate(ranked):
        result = item["metrics"][selection_key]
        if result["risk_breached"] or item["id"] in retiring:
            if result["risk_breached"]:
                reason = result["death_reason"] or "RISK_LIMIT_OR_MARGIN"
            elif result["trades"] == 0:
                reason = "INACTIVE_AFTER_PROBATION"
            else:
                reason = "PERSISTENT_UNPROFITABLE"
            removed.append({**item, "from_floor":item["floor"], "floor":0,
                            "status":"archived", "reason":reason})
            continue
        promising = (result["return_pct"] > 0 and result["fitness"] > 0
                     and result["closed_trades"] >= 2
                     and result["drawdown_pct"] <= 12)
        kept.append({**item, "floor":_floor(result,i),
                     "status":("probation" if item["probation_streak"] else
                               "research_leader" if promising and i == 0 else
                               "competing")})
    # Replacement happens only when a genuine vacancy opens.
    # Breeding from a losing or non-trading parent would reinforce the failure.
    rng=random.Random(state["seed"]+gen*10007)
    parents=[x for x in kept if x["metrics"][selection_key]["return_pct"]>0
             and x["metrics"][selection_key]["fitness"]>0
             and x["metrics"][selection_key]["closed_trades"]>=2]
    births=[]
    for slot in range(len(ranked)-len(kept)):
        parent=parents[slot%len(parents)] if parents else None
        mutated=([round(max(-3,min(3,g+rng.gauss(0,0.06))),8)
                  for g in parent["genes"]] if parent else
                 _new_genes(rng,explore_side="BUY" if (gen+slot)%2 else "SELL"))
        child={"id":f"ATL-G{gen}-{slot+1:03d}","generation":gen,
               "parent_id":parent["id"] if parent else None,
               "origin":"PARENT_MUTATION" if parent else "DIRECTIONAL_RESEARCH_EXPLORER",
               "genes":mutated,"genome_sha256":_digest(mutated),
               "floor":1, "status":"nursery", "metrics":None,
               "assessments":0, "probation_streak":0}
        births.append(child)
    next_state={**state,"generation":gen,"population":kept+births,
                "real_generation":(state.get("real_generation",0)+1 if state.get("real_data") else None),
                "total_born":state["total_born"]+len(births),
                "total_culled":state["total_culled"]+len(removed),
                "survival_policy":"MERIT_AND_PROBATION_V2"}
    events=[{"type":"GENERATION_EVALUATED","generation":gen,"kept_ids":[x["id"] for x in kept],
             "removed":[{"id":r["id"],"from_floor":r["from_floor"],"reason":r["reason"],
                         "selection":r["metrics"][selection_key]} for r in removed],
             "born":[{"id":b["id"],"parent_id":b["parent_id"]} for b in births],
             "source_kind":("REAL_XAUUSD_BID_ASK_RESEARCH_UNQUALIFIED" if state.get("real_data")
                            else "SYNTHETIC_RANDOM_WALK_ONLY"),
             "survival_policy":"MERIT_AND_PROBATION_V2",
             "probation_after":PROBATION_ASSESSMENTS,
             "max_nonrisk_retirements":MAX_PROBATION_RETIREMENTS,
             "probation_count":sum(a["status"]=="probation" for a in kept),
             "entry_diagnostics":{
                 "evaluated_agents":len(ranked),
                 "training_entries_total":sum(a["metrics"]["training"]["trades"] for a in ranked),
                 "diagnostic_entries_total":sum(a["metrics"]["selection"]["trades"] for a in ranked),
                 "training_inactive_agents":sum(a["metrics"]["training"]["trades"]==0 for a in ranked),
                 "diagnostic_inactive_agents":sum(a["metrics"]["selection"]["trades"]==0 for a in ranked),
                 "source_kind":("REAL_XAUUSD_BID_ASK_RESEARCH_UNQUALIFIED" if state.get("real_data")
                                else "SYNTHETIC_RANDOM_WALK_ONLY"),
                 "order_execution":False,
             },
             "selection_is_not_validation":True,
             "ranking_source":selection_key,
             "source_sha256":state.get("real_data",{}).get("source_sha256")}]
    return next_state,events



def activate_real_history(state: dict, snapshot: dict) -> tuple[dict, list[dict]]:
    """Explicitly switch the EXISTING cohort to immutable real quotes.

    Prior synthetic generations and archive survive. Real generations start at
    zero but the monotonic generation ID continues, avoiding archive collisions.
    """
    from agentic_trading.evolution_tower_real import validated_research_snapshot
    if state.get("schema") != "atl_evolution_tower.v1":
        raise TowerError("Unknown evolution tower schema")
    if state.get("real_data") is not None:
        raise TowerError("Real research source is already frozen; no cherry-picking replacement")
    if state["generation"] >= GENERATION_LIMIT-1:
        raise TowerError("Generation limit leaves no room to activate real history")
    real_data = validated_research_snapshot(snapshot)
    next_generation = state["generation"] + 1
    population = [{**agent, "metrics":None, "floor":1, "status":"nursery",
                   "assessments":0, "probation_streak":0}
                  for agent in state["population"]]
    next_state = {**state, "generation":next_generation,
                  "real_generation":0, "real_data":real_data,
                  "mode":"REAL_XAUUSD_BID_ASK_RESEARCH",
                  "population":population}
    event = {
        "type":"HISTORICAL_MODE_ACTIVATED", "generation":next_generation,
        "kept_ids":[a["id"] for a in population], "removed":[], "born":[],
        "source_kind":"REAL_XAUUSD_BID_ASK_RESEARCH_UNQUALIFIED",
        "source_sha256":real_data["source_sha256"],
        "working_sha256":real_data["working_sha256"],
        "provider":real_data["provider"], "ranking_source":"training",
        "selection_is_not_validation":True,
    }
    return next_state, [event]

def public_state(state: dict, events: list[dict]|None=None) -> dict:
    """Never expose strategy chromosomes or any qualification claim to browser."""
    real_data = state.get("real_data")
    return {
        **{k:v for k,v in state.items() if k not in ("population", "real_data")},
        "agents":[{k:v for k,v in agent.items() if k!="genes"}
                  for agent in state["population"]],
        "last_events":events or [],
        "champions":[],"penthouse_locked":True,"qualification":"unqualified",
        "baseline":"FLAT_ZERO_TRADE",
        "performance_kind":"REAL_HISTORICAL_QUOTES_UNQUALIFIED" if real_data else "TOY_SYNTHETIC_ONLY",
        "research_data":({k:v for k,v in real_data.items() if k!="bars"} if real_data else None),
        "worker_mode":"MANUAL_OR_BROWSER_OPEN","final_slice_d_accessed":False,
        "note":("Historical XAUUSD bid/ask replay with assumed slippage, fees and financing. "
                "B is used for evolution; C is repeatedly observed for diagnostics and cannot "
                "be independent validation; D is withheld. No demonstrated edge or trading authority."
                if real_data else
                "Research demonstration on deterministic synthetic random walks. "
                "Floor reflects relative toy-simulation fitness, not a market edge. "
                "No broker, independent alpha or background VPS worker."),
    }
