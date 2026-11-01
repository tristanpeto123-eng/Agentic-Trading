"""Real BID/ASK Evolution Tower regressions; test quotes are synthetic fixtures."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import copy

import pytest

from agentic_trading.evolution_tower import (
    TowerError, initial_state, activate_real_history, advance_state,
    public_state, GENES, _digest,
)
from agentic_trading.evolution_tower_real import (
    validated_research_snapshot, replay_bidask,
)
from agentic_trading.providers.xauusd_bidask import _pair, _snapshot


def quote_fixture(size=800):
    """Fixture exercises real quote semantics; NOT a claim of real market data."""
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(size):
        px = Decimal("3000.00") + Decimal(i % 97) / 10
        bid = dict(open=px, high=px+1, low=px-1,
                   close=px+Decimal("0.10"))
        ask = {key:value+Decimal("0.30") for key,value in bid.items()}
        bars.append(_pair(now+timedelta(minutes=15*i),bid,ask,42))
    return _snapshot("OANDA v20 practice BID/ASK", bars,
                     source="https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles")


def test_real_quote_data_freezes_and_omits_final_holdout():
    snap=quote_fixture()
    source=validated_research_snapshot(snap)
    assert source["observations_received"] == 800
    assert source["b_end"] == 560
    assert source["c_end"] == 720
    assert source["d_bars_withheld"] == 80
    assert len(source["bars"]) == 720
    assert source["working_sha256"] == _digest(source["bars"])
    assert snap["source_sha256"] == source["source_sha256"]
    assert snap["bars"][-1] not in source["bars"]


def test_switch_preserves_cohort_and_prevents_cherry_picked_replacement():
    state=initial_state(2026)
    first,events=advance_state(state)
    before={a["id"]:a["genome_sha256"] for a in first["population"]}
    switched,ev=activate_real_history(first,quote_fixture())
    assert switched["generation"]==first["generation"]+1
    assert switched["real_generation"]==0
    assert {a["id"]:a["genome_sha256"] for a in switched["population"]}==before
    assert ev[0]["type"]=="HISTORICAL_MODE_ACTIVATED"
    assert not ev[0]["removed"] and not ev[0]["born"]
    visible=public_state(switched,ev)
    assert "real_data" not in visible and "bars" not in visible["research_data"]
    assert visible["performance_kind"]=="REAL_HISTORICAL_QUOTES_UNQUALIFIED"
    assert visible["penthouse_locked"] and not visible["champions"]
    advanced,events=advance_state(copy.deepcopy(switched))
    again,other=advance_state(copy.deepcopy(switched))
    assert (advanced,events)==(again,other)
    assert advanced["real_generation"]==1
    assert advanced["population"][0]["metrics"]["source_kind"]=="REAL_XAUUSD_BID_ASK_RESEARCH_UNQUALIFIED"
    assert events[0]["ranking_source"]=="training"
    assert len(advanced["population"])==16
    with pytest.raises(TowerError,match="already frozen"):
        activate_real_history(switched,quote_fixture())


def test_exact_bid_ask_execution_and_integrity_failure():
    source=validated_research_snapshot(quote_fixture())
    genes=[0.0]*GENES
    genes[89]=4.0  # always buy
    report=replay_bidask(genes,source["bars"][:source["b_end"]])
    assert report["trades"]>0
    assert report["cost_usd"]>0
    assert report["risk_breached"] is False
    idle=[0.0]*GENES
    idle[88]=5.0  # always hold
    flat=replay_bidask(idle,source["bars"][:source["b_end"]])
    assert flat["trades"]==0 and flat["return_pct"]==0.0
    tampered=quote_fixture()
    tampered["bars"][0]["bid"]["close"]="3100"
    with pytest.raises(TowerError,match="hash mismatch"):
        validated_research_snapshot(tampered)
    state,_=activate_real_history(initial_state(),quote_fixture())
    state["real_data"]["bars"][0]["bid"]["close"]="3000.999"
    with pytest.raises(TowerError,match="integrity"):
        advance_state(state)


def test_route_requires_opted_in_real_feed_and_csrf(tmp_path,monkeypatch):
    from test_historical_render import _setup
    import agentic_trading.api as api_module

    client,headers,factory,engine=_setup(tmp_path,monkeypatch)
    started=client.post("/v1/evolution-tower/start",headers=headers,json={})
    assert started.status_code==200
    payload={"expected_generation":0,"source":"oanda"}
    denied=client.post("/v1/evolution-tower/use-real-history",json=payload)
    assert denied.status_code==403
    monkeypatch.delenv("ATL_OANDA_PRACTICE_RESEARCH",raising=False)
    disabled=client.post("/v1/evolution-tower/use-real-history",headers=headers,json=payload)
    assert disabled.status_code==409
    monkeypatch.setenv("ATL_OANDA_PRACTICE_RESEARCH","1")
    monkeypatch.setattr(api_module,"fetch_oanda_practice",lambda *,token:quote_fixture())
    activated=client.post("/v1/evolution-tower/use-real-history",headers=headers,json=payload)
    assert activated.status_code==200,activated.text
    response=activated.json()
    assert response["mode"]=="REAL_XAUUSD_BID_ASK_RESEARCH"
    assert response["generation"]==1
    assert "real_data" not in response
    assert response["research_data"]["d_bars_withheld"]==80
    step=client.post("/v1/evolution-tower/advance",headers=headers,
                     json={"expected_generation":1})
    assert step.status_code==200,step.text
    assert step.json()["real_generation"]==1
    engine.dispose()
