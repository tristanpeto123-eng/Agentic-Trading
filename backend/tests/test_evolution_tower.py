"""Research-only Evolution Tower: actual saved chromosomes, fixed risk, archive."""
import copy
from hashlib import sha256

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
    assert first["total_culled"]>=8
    assert first["total_born"]==POPULATION+first["total_culled"]
    assert events[0]["removed"] and events[0]["born"]
    assert len({a["id"] for a in first["population"]})==POPULATION
    old={a["id"]:a for a in state["population"]}
    for agent in first["population"]:
        if agent["id"] in old:
            assert agent["genes"]==old[agent["id"]]["genes"]
            assert agent["genome_sha256"]==old[agent["id"]]["genome_sha256"]
        else:
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
    assert result["last_events"][0]["removed"]
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
