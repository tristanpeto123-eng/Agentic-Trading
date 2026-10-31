from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from agentic_trading.five_batch_policy import (
    ClosedBatch, ClosedTrade, PolicyResearchError, propose_five_batch_policy,
)

BASE = datetime(2026, 10, 1, tzinfo=timezone.utc)
CATALOG_SHA = "a" * 64


def sample_batches(student_id="btc-student"):
    batches = []
    for i in range(5):
        end = BASE + timedelta(days=i + 1)
        trades = tuple(
            ClosedTrade(
                trade_id=f"trade-{i}-{j}", skill_id="trend",
                net_r=Decimal("0.5"), closed_at=end - timedelta(hours=2),
                available_at=end - timedelta(hours=1),
            )
            for j in range(2)
        )
        batches.append(ClosedBatch(
            batch_id=f"batch-{i}", student_id=student_id,
            market="BTCUSD", completed_at=end, trades=trades,
        ))
    return batches


def call(batches=None, **kwargs):
    base = {
        "student_id": "btc-student",
        "market": "BTCUSD",
        "as_of": BASE + timedelta(days=7),
        "skill_catalog_sha256": CATALOG_SHA,
        "allowed_skills": ["trend", "range"],
        "incumbent_scores": {"trend": "0.25", "range": "0.75"},
        "incumbent_version": 2,
        "batches": sample_batches() if batches is None else batches,
    }
    base.update(kwargs)
    return propose_five_batch_policy(**base)


def test_five_batches_create_deterministic_unapplied_research_candidate():
    report = call()
    assert report == call()
    assert report["from_version"] == 2
    assert report["candidate_version"] == 3
    assert report["completed_batch_count"] == 5
    assert report["closed_train_trade_count"] == 10
    assert report["candidate_scores"] == {"trend": "0.350000", "range": "0.750000"}
    assert report["skill_evidence"]["range"] == {"train_trades": 0, "changed": False}
    assert report["skill_catalog_sha256"] == CATALOG_SHA
    assert len(report["candidate_sha256"]) == 64
    assert report["status"] == "awaiting_independent_validation"
    assert not report["applied_to_student"]
    assert not report["qualified"]
    assert not report["paper_trading_enabled"]
    assert not report["live_trading_enabled"]


def test_rejects_fewer_or_duplicate_batches():
    batches = sample_batches()
    with pytest.raises(PolicyResearchError, match="exactly five"):
        call(batches[:4])
    with pytest.raises(PolicyResearchError, match="duplicate"):
        call(batches[:4] + [batches[0]])


def test_rejects_mixed_student_and_market():
    batches = sample_batches()
    batches[4] = replace(batches[4], student_id="other-student")
    with pytest.raises(PolicyResearchError, match="cross-student"):
        call(batches)
    batches = sample_batches()
    batches[4] = replace(batches[4], market="XAUUSD")
    with pytest.raises(PolicyResearchError, match="cross-student"):
        call(batches)


@pytest.mark.parametrize(("change", "value"), [
    ("partition", "test"),
    ("origin", "independent_holdout"),
    ("skill_id", "unapproved-skill"),
    ("net_r", Decimal("NaN")),
])
def test_rejects_unqualified_trade_inputs(change, value):
    batches = sample_batches()
    bad = replace(batches[4].trades[0], **{change: value})
    batches[4] = replace(batches[4], trades=(bad, batches[4].trades[1]))
    with pytest.raises(PolicyResearchError):
        call(batches)


def test_rejects_future_or_unclosed_evidence():
    batches = sample_batches()
    bad = replace(batches[4].trades[0],
                  available_at=batches[4].completed_at + timedelta(minutes=1))
    batches[4] = replace(batches[4], trades=(bad, batches[4].trades[1]))
    with pytest.raises(PolicyResearchError, match="future"):
        call(batches)


def test_rejects_skill_catalog_mutation_and_invalid_time():
    with pytest.raises(PolicyResearchError, match="preserve the frozen"):
        call(allowed_skills=["trend", "range", "new-skill"])
    with pytest.raises(PolicyResearchError, match="timezone-aware UTC"):
        call(as_of=BASE.replace(tzinfo=None))


def test_candidate_does_not_mutate_incumbent_policy():
    incumbent = {"trend": "0.25", "range": "0.75"}
    original = dict(incumbent)
    proposed = call(incumbent_scores=incumbent)
    assert incumbent == original
    assert proposed["previous_scores"] == {"trend": "0.250000", "range": "0.750000"}
    assert proposed["candidate_scores"] != proposed["previous_scores"]
