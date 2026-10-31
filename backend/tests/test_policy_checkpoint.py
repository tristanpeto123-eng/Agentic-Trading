"""S13 research-only persistent five-batch checkpoint integration tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect

from agentic_trading.five_batch_policy import ClosedBatch, ClosedTrade, PolicyResearchError
from agentic_trading.policy_checkpoint import checkpoint_five_batches, research_policy_history
from agentic_trading.skills_memory import (
    ClosedTradeEpisode, Origin, ExamPartition, append_episode,
)
from agentic_trading.storage import (
    Base, LearningPlan, ResearchPolicyCandidate, Student, TradeExperience,
    new_session_factory,
)

START = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)


def setup(tmp_path):
    engine, factory = new_session_factory(f"sqlite:///{tmp_path / 'policy.sqlite3'}")
    Base.metadata.create_all(engine)
    with factory() as session:
        a = Student(name="Orion", name_key="orion")
        b = Student(name="Nova", name_key="nova")
        session.add_all([a, b])
        session.flush()
        session.add_all([
            LearningPlan(student_id=a.id, version=1, mode="directed",
                         markets=["XAUUSD"], skills=["trend"], reason="scoped"),
            LearningPlan(student_id=b.id, version=1, mode="autonomous",
                         markets=[], skills=[], reason="research"),
        ])
        session.commit()
        ids = a.id, b.id
    return engine, factory, *ids


def make_episode(student_id, date, *, partition=ExamPartition.TRAIN):
    return ClosedTradeEpisode(
        event_id=uuid4(), student_id=UUID(student_id),
        source_id="fixture:research", source_sha256="a" * 64,
        origin=Origin.SYNTHETIC_FIXTURE, partition=partition,
        instrument="XAUUSD", strategy_version="r1", proposal_sha256="b" * 64,
        skill_ids=("market:XAUUSD", "risk:risk_management", "tactic:trend"),
        signal_at=date, opened_at=date + timedelta(minutes=1),
        closed_at=date + timedelta(minutes=15),
        available_at=date + timedelta(minutes=16), initial_risk_usd=Decimal("10"),
        gross_pnl_usd=Decimal("15"), spread_cost_usd=Decimal("1"),
        slippage_cost_usd=Decimal("1"), fees_usd=Decimal("1"),
        mfe_r=Decimal("2"), mae_r=Decimal("0.5"), close_reason="target",
        market_regime="TREND_UP",
    )


def seeded_batches(session, student_id):
    out = []
    for i in range(5):
        date = START + timedelta(days=i)
        event = make_episode(student_id, date)
        append_episode(session, event)
        out.append(ClosedBatch(
            batch_id=f"batch-{i}", student_id=student_id, market="XAUUSD",
            completed_at=event.available_at + timedelta(minutes=1),
            trades=(ClosedTrade(
                trade_id=str(event.event_id), skill_id="tactic:trend", net_r=event.net_r,
                closed_at=event.closed_at, available_at=event.available_at,
                partition="train", origin="synthetic_fixture",
            ),),
        ))
    session.commit()
    return tuple(out)


def test_checkpoint_persists_exactly_once_without_promoting(tmp_path):
    engine, factory, sid, _ = setup(tmp_path)
    with factory() as session:
        batches = seeded_batches(session, sid)
        candidate = checkpoint_five_batches(
            session, student_id=sid, market="XAUUSD", batches=batches,
            as_of=START + timedelta(days=6),
        )
        again = checkpoint_five_batches(
            session, student_id=sid, market="XAUUSD", batches=batches,
            as_of=START + timedelta(days=6),
        )
        assert again.id == candidate.id
        assert candidate.version == 2
        history = research_policy_history(session, sid)
        assert len(history) == 1
        assert history[0]["status"] == "awaiting_independent_validation"
        assert history[0]["candidate_scores"] == {"tactic:trend": "0.600000"}
        assert history[0]["paper_trading_enabled"] is False
        assert history[0]["applied_to_student"] is False
        assert len(session.query(ResearchPolicyCandidate).all()) == 1
    engine.dispose()


def test_source_truth_refuses_mixed_student_tamper_and_holdout(tmp_path):
    engine, factory, sid, other = setup(tmp_path)
    with factory() as session:
        batches = list(seeded_batches(session, sid))
        bad_trade = replace(batches[0].trades[0], net_r=Decimal("999"))
        batches[0] = replace(batches[0], trades=(bad_trade,))
        with pytest.raises(PolicyResearchError, match="archived student TRAIN"):
            checkpoint_five_batches(
                session, student_id=sid, market="XAUUSD", batches=tuple(batches),
                as_of=START + timedelta(days=6),
            )
        batches = seeded_batches(session, other)
        with pytest.raises(PolicyResearchError, match="archived student TRAIN"):
            checkpoint_five_batches(
                session, student_id=sid, market="XAUUSD", batches=batches,
                as_of=START + timedelta(days=6),
            )
        assert research_policy_history(session, sid) == []
    engine.dispose()


def test_reject_duplicate_candidate_version_and_corrupted_history(tmp_path):
    engine, factory, sid, _ = setup(tmp_path)
    with factory() as session:
        batches = seeded_batches(session, sid)
        c = checkpoint_five_batches(
            session, student_id=sid, market="XAUUSD", batches=batches,
            as_of=START + timedelta(days=6),
        )
        with pytest.raises(PolicyResearchError, match="version collision"):
            checkpoint_five_batches(
                session, student_id=sid, market="XAUUSD", batches=batches,
                as_of=START + timedelta(days=7),
            )
        c.payload = {**c.payload, "qualified": True}
        session.commit()
        with pytest.raises(PolicyResearchError, match="integrity violation"):
            research_policy_history(session, sid)
    engine.dispose()


def test_not_an_api_or_an_active_order_strategy(tmp_path):
    engine, factory, sid, _ = setup(tmp_path)
    assert "research_policy_candidates" in inspect(engine).get_table_names()
    with factory() as session:
        batches = seeded_batches(session, sid)
        c = checkpoint_five_batches(
            session, student_id=sid, market="XAUUSD", batches=batches,
            as_of=START + timedelta(days=6),
        )
        assert c.state == "awaiting_independent_validation"
        assert not any(s.status == "trading" for s in session.query(Student))
    engine.dispose()
