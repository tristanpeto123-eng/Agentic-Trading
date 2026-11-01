"""Synthetic-only tests: no reported result demonstrates market profitability."""
from dataclasses import replace
from decimal import Decimal
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autolabel
from foundation import (CostContract, FoundationError, create_manifest,
                        label_cost_ledger, prepare_skill_A, research_partition,
                        validated_frame)


def prices(n=2800):
    frame = autolabel.demo_data(n=n, seed=17)
    frame["time"] = frame["time"].dt.tz_localize("UTC")
    frame["spread"] = .00017
    frame["financing_long"] = 0.0
    frame["financing_short"] = 0.0
    # Mock broker rollover charges with explicit zero/no-rollover bars.
    frame.loc[frame.time.dt.hour == 22, "financing_long"] = .000013
    frame.loc[frame.time.dt.hour == 22, "financing_short"] = .000009
    return frame


def contract():
    return CostContract(slippage_entry=Decimal("0.00003"),
                        slippage_exit=Decimal("0.00004"),
                        commission_per_side=Decimal("0.00002"),
                        source_reference="SYNTHETIC_TEST_NOT_BROKER")


def manifest(frame):
    return create_manifest(frame, instrument="EURUSD", provider_reference="SYNTHETIC_TEST_FIXTURE",
                           rights_reference="SYNTHETIC_TEST_ONLY")


def test_exact_time_ordered_quarantine_and_sealed_d():
    frame=prices(2800); info=manifest(frame)
    assert (info.a_end,info.b_end,info.c_end,info.n_bars)==(1400,2100,2520,2800)
    assert info.qualified is False
    a=research_partition(frame,info,part="A",purpose="skill_training")
    b=research_partition(frame,info,part="B",purpose="bot_training")
    c=research_partition(frame,info,part="C",purpose="selection")
    assert len(a)==1400 and len(b)==700 and len(c)==420
    assert a.time.iloc[-1]<b.time.iloc[0]<c.time.iloc[0]
    with pytest.raises(FoundationError,match="sealed D"):
        research_partition(frame,info,part="D",purpose="final_test")
    with pytest.raises(FoundationError,match="role mismatch"):
        research_partition(frame,info,part="C",purpose="bot_training")
    altered=frame.copy();altered.loc[2700,"close"]+=.0001
    with pytest.raises(FoundationError,match="hash mismatch"):
        research_partition(altered,info,part="A",purpose="skill_training")
    a.loc[0,"close"]+=1
    assert frame.loc[0,"close"]!=a.loc[0,"close"]


def test_bad_utc_missing_costs_duplicate_gaps_rejected():
    data=prices(150)
    with pytest.raises(FoundationError,match="exactly"):
        validated_frame(data.drop(columns="spread"))
    naive=data.copy();naive["time"]=naive.time.dt.tz_localize(None)
    with pytest.raises(FoundationError,match="UTC"):
        validated_frame(naive)
    duplicate=data.copy();duplicate.loc[5,"time"]=duplicate.loc[4,"time"]
    with pytest.raises(FoundationError,match="unique"):
        validated_frame(duplicate)
    wrong=data.copy();wrong.loc[0,"spread"]=0
    with pytest.raises(FoundationError,match="strictly positive"):
        validated_frame(wrong)
    weird=data.copy();weird.loc[8,"time"]+=pd.Timedelta(minutes=7)
    with pytest.raises(FoundationError,match="align"):
        validated_frame(weird)
    missing=data.drop(index=[70]).reset_index(drop=True)
    assert manifest(missing).gaps==1  # Never fabricate missing prices.


def test_missing_cost_contract_is_not_implicit():
    with pytest.raises(TypeError):
        CostContract()  # no spread, slippage, commission or finance defaults
    with pytest.raises(FoundationError,match="source reference"):
        CostContract(Decimal("0"),Decimal("0"),Decimal("0"),"")
    with pytest.raises(FoundationError,match="nonnegative"):
        CostContract(Decimal("-1"),Decimal("0"),Decimal("0"),"TEST_SOURCE")


def simple_frame(n=125):
    df=pd.DataFrame({"time":pd.date_range("2025-01-01",periods=n,freq="15min",tz="UTC"),
                     "open":100.,"high":100.5,"low":99.5,"close":100.,
                     "volume":50.,"spread":.2,
                     "financing_long":0.,"financing_short":0.})
    return df


def test_tp_first_gross_y_unchanged_but_costs_can_turn_win_into_loss():
    frame=simple_frame()
    frame.loc[51,"high"]=103.
    df=pd.DataFrame({"i":[50],"t_end":[51.],"direction":[1],"y":[1.]})
    fees=CostContract(Decimal("0.6"),Decimal("0.6"),Decimal("0.12"),"EXPLICIT_SYNTHETIC")
    audit=label_cost_ledger(frame,df,fees)
    assert audit.y.iloc[0]==1.
    assert audit.exit_reason.iloc[0]=="TP"
    assert audit.gross_pnl_per_unit.iloc[0]==pytest.approx(2.)
    assert audit.spread_cost_per_unit.iloc[0]==pytest.approx(.2)
    assert audit.commission_cost_per_unit.iloc[0]==pytest.approx(.24)
    assert audit.total_cost_per_unit.iloc[0]==pytest.approx(1.64)
    assert audit.net_pnl_per_unit.iloc[0]==pytest.approx(.36)
    more=CostContract(Decimal("1"),Decimal("1"),Decimal(".12"),"EXPLICIT_SYNTHETIC")
    expensive=label_cost_ledger(frame,df,more)
    assert expensive.y.iloc[0]==1.
    assert expensive.net_profitable.iloc[0]==0
    assert expensive.net_r.iloc[0]<0


def test_stop_first_and_stop_gap_use_worse_opening_price():
    frame=simple_frame()
    frame.loc[51,"high"]=103.;frame.loc[51,"low"]=98.
    one=pd.DataFrame({"i":[50],"t_end":[51.],"direction":[1],"y":[0.]})
    audit=label_cost_ledger(frame,one,contract())
    assert audit.exit_reason.iloc[0]=="STOP"
    assert audit.mid_exit.iloc[0]==pytest.approx(99.)
    gap=simple_frame();gap.loc[52,["open","close","high","low"]]=[98.,98.,98.5,97.]
    gap_df=pd.DataFrame({"i":[50],"t_end":[52.],"direction":[1],"y":[0.]})
    r=label_cost_ledger(gap,gap_df,contract())
    assert r.mid_exit.iloc[0]==pytest.approx(98.)
    assert r.gross_pnl_per_unit.iloc[0]==pytest.approx(-2.)


def test_financing_uses_each_brokers_booking_side_and_no_invented_costs():
    df=simple_frame();df.loc[54,"high"]=103.;df.loc[54,"financing_long"] = .32
    ds=pd.DataFrame({"i":[50],"t_end":[54.],"direction":[1],"y":[1.]})
    a=label_cost_ledger(df,ds,contract())
    assert a.financing_cost_per_unit.iloc[0]==pytest.approx(.32)
    assert a.net_pnl_per_unit.iloc[0]==pytest.approx(
        a.gross_pnl_per_unit.iloc[0]-a.total_cost_per_unit.iloc[0])


def test_only_slice_a_gets_skill_labels_and_cost_report_is_unqualified():
    df=prices(2800);m=manifest(df)
    ledger,report=prepare_skill_A(df,m,skill="fvg",costs=contract())
    assert report["qualification_allowed"] is False
    assert report["broker_execution_allowed"] is False
    assert report["slice"]=="A"
    assert report["labels_cost_audited"]==len(ledger)
    assert len(ledger)>10
    assert ledger["i"].max()<m.a_end
    assert ledger["t_end"].max()<m.a_end
    assert set(ledger.y.unique()).issubset({0.,1.})
    assert (ledger.total_cost_per_unit>0).all()
    # TP-first y is maintained as an independent column, even if net is negative.
    assert (ledger.net_profitable.isin([0,1])).all()


def test_single_change_to_post_a_rows_does_not_change_a_labels():
    df=prices(2800);m=manifest(df)
    ledger,_=prepare_skill_A(df,m,skill="fvg",costs=contract())
    changed=df.copy()
    changed.loc[2300:,["open","high","low","close"]]*=1.3
    # Build a different manifest for the changed immutable dataset.
    fresh=manifest(changed)
    new,_=prepare_skill_A(changed,fresh,skill="fvg",costs=contract())
    pd.testing.assert_frame_equal(ledger,new)


def test_forged_slice_boundaries_and_premature_timeout_rejected():
    frame=prices(2800);m=manifest(frame)
    with pytest.raises(FoundationError,match="Tampered"):
        research_partition(frame,replace(m,c_end=m.n_bars),part="C",purpose="selection")
    df=simple_frame()
    premature=pd.DataFrame({"i":[50],"t_end":[52.],"direction":[1],"y":[0.]})
    with pytest.raises(FoundationError,match="Timeout"):
        label_cost_ledger(df,premature,contract())
    missing=premature.drop(columns="direction")
    with pytest.raises(FoundationError,match="direction"):
        label_cost_ledger(df,missing,contract())
