"""Research-only Evolution Tower: actual saved chromosomes, fixed risk, archive."""
import copy
from hashlib import sha256
import agentic_trading.evolution_tower as tower

import pytest
from sqlalchemy import select

from agentic_trading.evolution_tower import (
    POPULATION, GENES, TowerError, initial_state, advance_state,
    evaluate, make_tape, public_state, _digest,
)
from agentic_trading.storage import (
    EvolutionTowerSession, EvolutionTowerArchive,
    Base, new_session_factory,
)
from test_historical_render import _setup


def test_generation_mutates_real_weights_and_preserves_archive_without_a_fake_champion():
    state=initial_state(seed=112233)
    assert state["generation"]==0 and len(state["population"])==16
    assert len({a["genome_sha256"] for a in state["population"]})==16
    assert all(len(a["genes"])==GENES for a in state["population"])
    first,events=advance_state(copy.deepcopy(state))
    second,again=advance_state(copy.deepcopy(state))
    assert first==second and events==again
    assert first["generation"]==1
    assert len(first["population"])==POPULATION
    # Ranking does not impose a mandatory 50% purge.
    assert first["total_culled"] <= POPULATION
    assert events[0]["survival_policy"] == "MERIT_AND_PROBATION_V2"
    assert len(events[0]["removed"]) == first["total_culled"]
    assert first["total_born"]==POPULATION+first["total_culled"]
    assert len(events[0]["removed"]) == len(events[0]["born"])
    assert len({a["id"] for a in first["population"]})==POPULATION
    old={a["id"]:a for a in state["population"]}
    for agent in first["population"]:
        if agent["id"] in old:
            assert agent["genes"]==old[agent["id"]]["genes"]
            assert agent["genome_sha256"]==old[agent["id"]]["genome_sha256"]
        else:
            if agent["parent_id"] is not None:
                assert agent["parent_id"] in old
                assert agent["genome_sha256"] != old[agent["parent_id"]]["genome_sha256"]
        assert agent["floor"]<=49
    public=public_state(first,events)
    assert not public["champions"] and public["penthouse_locked"]
    assert public["final_slice_d_accessed"] is False
    assert public["performance_kind"]=="TOY_SYNTHETIC_ONLY"
    assert all("genes" not in a for a in public["agents"])
    assert first["mode"]=="SYNTHETIC_ONLY"
    assert first["paper_trading_enabled"] is False
    assert first["live_trading_enabled"] is False


def _test_grade(genes, _generation, _real_data=None):
    """Stable fake metrics to test selection policy separately from price replay."""
    index=round(genes[0]*10)
    if index == 15:
        ret, trades, risk = -25., 2, True
    elif index in (13,14):
        ret, trades, risk = 0., 0, False
    elif index in (11,12):
        ret, trades, risk = -1., 4, False
    else:
        ret, trades, risk = 2., 4, False
    metric={"return_pct":ret,"trades":trades,
            "closed_trades":trades, "drawdown_pct":0 if ret>=0 else abs(ret),
            "fitness":ret, "risk_breached":risk,
            "death_reason":"RISK_LIMIT_OR_MARGIN" if risk else None}
    return {"training":metric,"selection":metric,"source_kind":"SYNTHETIC_RANDOM_WALK_ONLY"}


def test_merit_survival_no_compulsory_half_population_cull(monkeypatch):
    monkeypatch.setattr(tower,"_grade",_test_grade)
    state=initial_state(seed=55)
    for i,agent in enumerate(state["population"]):
        agent["genes"][0]=i/10
        agent["genome_sha256"]=_digest(agent["genes"])
    current,event=advance_state(state)
    # One genuine risk breach, not eight forced selection deaths.
    assert len(event[0]["removed"])==1
    assert event[0]["removed"][0]["reason"]=="RISK_LIMIT_OR_MARGIN"
    assert current["total_culled"]==1
    assert len(current["population"])==16
    assert all(a["id"] in {x["id"] for x in current["population"]}
               for a in state["population"][:11])
    assert current["population"][0]["assessments"]==1
    assert sum(a["status"]=="probation" for a in current["population"])>=4
    assert all(a["probation_streak"]==0 for a in current["population"]
               if a["id"] in {x["id"] for x in state["population"][:11]})
    # Inactivity and losing entries remain through assessments 1 and 2.
    second,ev2=advance_state(current)
    assert not any(a["reason"].startswith(("INACTIVE","PERSISTENT"))
                   for a in ev2[0]["removed"])
    third,ev3=advance_state(second)
    nonrisk=[a for a in ev3[0]["removed"] if a["reason"]!="RISK_LIMIT_OR_MARGIN"]
    assert 0<len(nonrisk)<=tower.MAX_PROBATION_RETIREMENTS
    assert set(a["reason"] for a in nonrisk) <= {
        "INACTIVE_AFTER_PROBATION","PERSISTENT_UNPROFITABLE"}
    assert len(third["population"])==16
    assert len({a["id"] for a in third["population"]})==16
    assert all(a["floor"]<=49 for a in third["population"])
    assert public_state(third,ev3)["champions"]==[]


def test_every_profitable_bot_survives_even_with_low_rank(monkeypatch):
    def grade(genes,gen,real=None):
        n=round(genes[0]*10)
        score=.01+(.002*n)
        m={"return_pct":score,"fitness":score,"trades":2,"closed_trades":2,
           "drawdown_pct":1.,"risk_breached":False,"death_reason":None}
        return {"training":m,"selection":m,"source_kind":"SYNTHETIC_RANDOM_WALK_ONLY"}
    monkeypatch.setattr(tower,"_grade",grade)
    state=initial_state()
    for i,a in enumerate(state["population"]):
        a["genes"][0]=i/10
        a["genome_sha256"]=_digest(a["genes"])
    for _ in range(4):
        state,events=advance_state(state)
        assert len(events[0]["removed"])==0
        assert len(events[0]["born"])==0
        assert len(state["population"])==16
        assert state["total_culled"]==0
    assert all(a["assessments"]==4 for a in state["population"])


def test_recruit_exploration_is_real_neural_policy_not_fabricated_entries():
    state=initial_state(seed=112233)
    from agentic_trading.evolution_tower import _brain
    features=[0.0]*6
    # Some initial chromosomes are seeded to propose trades, while HOLD
    # remains available; no execution or guaranteed profitability is asserted.
    proposals=[_brain(a["genes"],features) for a in state["population"]]
    assert 1 in proposals and 2 in proposals
    assert len(state["population"])==16
    assert all(a["metrics"] is None for a in state["population"])
    first,events=advance_state(state)
    audit=events[0]["entry_diagnostics"]
    assert audit["evaluated_agents"]==16
    assert audit["order_execution"] is False
    assert audit["training_entries_total"]>=0
    assert audit["training_inactive_agents"]<=16
    assert len(first["population"])==16


def test_idle_agents_replaced_by_explorers_after_prolonged_probation(monkeypatch):
    from agentic_trading.evolution_tower import _brain
    def always_idle(_genes,_gen,_real=None):
        metrics={"trades":0,"return_pct":0.,"fitness":0.,"risk_breached":False,
                 "closed_trades":0,"drawdown_pct":0.,"death_reason":None}
        return {"training":metrics,"selection":metrics,"source_kind":"SYNTHETIC_RANDOM_WALK_ONLY"}
    monkeypatch.setattr(tower,"_grade",always_idle)
    state=initial_state(seed=77)
    for _ in range(3):
        state,event=advance_state(state)
    explorers=[a for a in state["population"]
               if a.get("origin")=="DIRECTIONAL_RESEARCH_EXPLORER"]
    assert 1<=len(explorers)<=tower.MAX_PROBATION_RETIREMENTS
    assert all(a["parent_id"] is None for a in explorers)
    assert all(_brain(a["genes"],[0.0]*6) in (1,2) for a in explorers)
    assert event[0]["entry_diagnostics"]["training_inactive_agents"]==16
    assert not public_state(state,event)["paper_trading_enabled"]


def test_fitness_includes_friction_and_bounded_risk_with_no_external_data():
    tape=make_tape(55,192)
    assert make_tape(55,192)==tape
    assert make_tape(56,192)!=tape
    # Force a fixed action preference: buy on first step, then hold.
    genes=[0.0]*GENES
    genes[89]=4.0  # output BUY (offset 88+1)
    report=evaluate(genes,tape)
    assert report["trades"]>=1
    assert report["cost_usd"]>0
    assert report["entry_samples"]
    assert report["entry_samples"][0]["side"]=="BUY"
    assert report["entry_samples"][0]["price_basis"]=="ASSUMED_SYNTHETIC_EXECUTION"
    assert report["drawdown_pct"]>=0
    assert report["fitness"]<100
    assert report["return_pct"]<20
    # Flat baseline incurs zero trades, cost and reward on a toy tape.
    idle=[0.0]*GENES
    idle[88]=5.0
    flat=evaluate(idle,tape)
    assert flat["trades"]==0 and flat["cost_usd"]==0.0
    assert flat["return_pct"]==0.0
    assert flat["fitness"]==0.0


def test_safety_blocks_corrupt_chromosome_and_caps_generations():
    state=initial_state()
    state["population"][0]["genes"][0]+=1
    with pytest.raises(TowerError,match="integrity"):
        advance_state(state)
    state=initial_state()
    state["generation"]=100
    with pytest.raises(TowerError,match="limit"):
        advance_state(state)


def test_api_requires_ceo_csrf_persists_restart_and_audits_every_generation(tmp_path,monkeypatch):
    client,headers,factory,engine=_setup(tmp_path,monkeypatch)
    assert client.post("/v1/evolution-tower/start").status_code==403
    initial=client.get("/v1/evolution-tower")
    assert initial.status_code==200 and not initial.json()["initialized"]
    started=client.post("/v1/evolution-tower/start",headers=headers,json={})
    assert started.status_code==200,started.text
    cohort=started.json()
    assert cohort["generation"]==0 and len(cohort["agents"])==16
    assert all("genes" not in x for x in cohort["agents"])
    assert not cohort["champions"] and not cohort["paper_trading_enabled"]
    second_start=client.post("/v1/evolution-tower/start",headers=headers,json={})
    assert second_start.status_code==200
    assert second_start.json()["state_sha256"]==cohort["state_sha256"]
    denied=client.post("/v1/evolution-tower/advance",json={"expected_generation":0})
    assert denied.status_code==403
    step=client.post("/v1/evolution-tower/advance",headers=headers,json={"expected_generation":0})
    assert step.status_code==200,step.text
    result=step.json()
    assert result["generation"]==1
    assert result["state_sha256"]!=cohort["state_sha256"]
    assert result["last_events"][0]["survival_policy"] == "MERIT_AND_PROBATION_V2"
    assert client.post("/v1/evolution-tower/advance",headers=headers,
                       json={"expected_generation":0}).status_code==409
    assert client.post("/v1/evolution-tower/advance",headers=headers,
                       json={"expected_generation":True}).status_code==422
    with factory() as session:
        record=session.scalar(select(EvolutionTowerSession))
        assert record.generation==1
        assert _digest(record.state)==record.state_sha256
        events=session.scalars(select(EvolutionTowerArchive)).all()
        assert len(events)==1 and _digest(events[0].event)==events[0].event_sha256
    engine.dispose()
    # New SQLAlchemy engine, persisted files, identical safe GET response.
    restored_engine,restored_factory=new_session_factory("sqlite:///"+str(tmp_path/"archive.sqlite3"))
    with restored_factory() as session:
        record=session.scalar(select(EvolutionTowerSession))
        assert record.generation==1
        assert record.state_sha256==result["state_sha256"]
        events=session.scalars(select(EvolutionTowerArchive)).all()
        assert len(events)==1 and events[0].event_sha256==_digest(events[0].event)
    restored_engine.dispose()
    client.cookies.clear()
    assert client.get("/v1/evolution-tower").status_code==401
