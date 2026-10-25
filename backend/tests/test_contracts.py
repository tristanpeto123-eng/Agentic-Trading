from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentic_trading.contracts import (
    EventEnvelope, EvidenceKind, Provenance, TradeProposal, TradeAssessment,
    GuardianDecision, Decision, CEOApproval, AuthorizationMode, ApprovalDecision,
    ResearchExamEvidence,
)
from agentic_trading.policy import approval_allows, can_promote_research, guardian_allows, research_execution_authorised

NOW = datetime(2026, 10, 25, 10, tzinfo=timezone.utc)
SHA_A = "a" * 64
SHA_B = "b" * 64

def proposal(**changes):
    args = dict(
        proposal_id=uuid4(), revision=1, student_id=uuid4(), strategy_version="trend-v1",
        model_sha256=SHA_A, instrument="XAUUSD", direction="LONG",
        entry_reference="4200", stop_price="4190", target_price="4220",
        tactic_id="trend", thesis="Directional continuation", invalidation="Trend broken",
        observed_data_available_at=NOW, created_at=NOW, expires_at=NOW + timedelta(minutes=15),
        content_sha256=SHA_B,
    )
    args.update(changes)
    return TradeProposal(**args)

def assessed_and_guarded(p):
    a = TradeAssessment(
        proposal_id=p.proposal_id, proposal_revision=p.revision,
        proposal_sha256=p.content_sha256, scout_b_model_sha256=SHA_A,
        expected_net_r=Decimal("0.3"), assessed_at=NOW + timedelta(seconds=2),
    )
    g = GuardianDecision(
        proposal_id=p.proposal_id, proposal_revision=p.revision,
        proposal_sha256=p.content_sha256, decision=Decision.APPROVED,
        reasons=("within predefined research controls",), decided_at=NOW + timedelta(seconds=3),
    )
    return a, g

def exam(**changes):
    args = dict(
        exam_id=uuid4(), student_id=uuid4(), challenger_model_sha256=SHA_A,
        champion_model_sha256=SHA_B, dataset_sha256=SHA_A,
        evidence_kind=EvidenceKind.HISTORICAL_VERIFIED,
        closed_trades=150, profit_factor="1.3", max_drawdown_fraction="0.10",
        net_pnl="250", champion_outperformed=True, integrity_passed=True,
        leakage_checks_passed=True, independently_reproduced=True,
        final_holdout_eligible=True,
    )
    args.update(changes)
    return ResearchExamEvidence(**args)

def approval(p, **changes):
    args = dict(
        approval_id=uuid4(), actor_id=uuid4(), actor_role="CEO", decision="APPROVED",
        student_id=p.student_id, model_sha256=p.model_sha256,
        strategy_version=p.strategy_version, mode="PAPER", instrument=p.instrument,
        account_id="demo-only", capital_limit="500", per_trade_risk_limit="0.01",
        leverage_limit="2", approved_at=NOW, expires_at=NOW + timedelta(days=1),
    )
    args.update(changes)
    return CEOApproval(**args)

def test_event_envelope_validates_provenance_and_time():
    e = EventEnvelope(
        schema_version="v1", event_type="MarketObservation.v1", event_id=uuid4(),
        correlation_id=uuid4(), producer="data_engine", occurred_at=NOW,
        available_at=NOW + timedelta(seconds=2), payload_sha256=SHA_A,
        provenance=Provenance(evidence_kind="historical_verified", source_id="provider-1", source_sha256=SHA_B),
    )
    e.assert_visible_at(NOW + timedelta(seconds=2))
    with pytest.raises(ValueError, match="future information"):
        e.assert_visible_at(NOW)
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate({**e.model_dump(), "available_at": NOW - timedelta(seconds=1)})

def test_event_negative_availability_is_rejected():
    with pytest.raises(ValidationError):
        EventEnvelope(
            schema_version="v1", event_type="E.v1", event_id=uuid4(), correlation_id=uuid4(),
            producer="test", occurred_at=NOW, available_at=NOW - timedelta(seconds=1),
            payload_sha256=SHA_A,
            provenance=Provenance(evidence_kind="synthetic", source_id="test", source_sha256=SHA_B),
        )

def test_proposal_rejects_future_data_and_bad_stops():
    with pytest.raises(ValidationError):
        proposal(observed_data_available_at=NOW + timedelta(minutes=1))
    with pytest.raises(ValidationError):
        proposal(stop_price="4205")
    with pytest.raises(ValidationError):
        proposal(direction="SHORT", stop_price="4190", target_price="4220")

def test_guardian_denial_blocks_all_research_orders():
    p = proposal()
    a, g = assessed_and_guarded(p)
    assert research_execution_authorised(p, a, g)
    assert not research_execution_authorised(p, a, g.model_copy(update={"decision": Decision.DENIED}))

def test_proposal_revision_requires_rescoring_and_reguarding():
    p = proposal()
    a, g = assessed_and_guarded(p)
    revised = proposal(proposal_id=p.proposal_id, student_id=p.student_id, revision=2, content_sha256=SHA_A)
    assert not guardian_allows(revised, a, g)

def test_ceo_approval_exact_identity_scope_and_expiry():
    p = proposal()
    ok = approval(p)
    assert approval_allows(ok, p, AuthorizationMode.PAPER, "demo-only", NOW + timedelta(minutes=1))
    assert not approval_allows(None, p, AuthorizationMode.PAPER, "demo-only", NOW + timedelta(minutes=1))
    assert not approval_allows(ok, p, AuthorizationMode.LIVE, "demo-only", NOW + timedelta(minutes=1))
    assert not approval_allows(ok, p, AuthorizationMode.PAPER, "other-account", NOW + timedelta(minutes=1))
    assert not approval_allows(ok, p, AuthorizationMode.PAPER, "demo-only", NOW + timedelta(days=2))
    assert not approval_allows(approval(p, model_sha256=SHA_B), p, AuthorizationMode.PAPER, "demo-only", NOW + timedelta(minutes=1))
    assert not approval_allows(approval(p, decision="REJECTED"), p, AuthorizationMode.PAPER, "demo-only", NOW + timedelta(minutes=1))

def test_research_promotion_needs_real_evidence_and_thresholds():
    assert can_promote_research(exam())
    assert not can_promote_research(exam(evidence_kind=EvidenceKind.SYNTHETIC))
    assert not can_promote_research(exam(evidence_kind=EvidenceKind.COUNTERFACTUAL))
    assert not can_promote_research(exam(closed_trades=99))
    assert not can_promote_research(exam(profit_factor="1.19"))
    assert not can_promote_research(exam(max_drawdown_fraction="0.16"))
    assert not can_promote_research(exam(net_pnl="0"))
    assert not can_promote_research(exam(champion_outperformed=False))
    assert not can_promote_research(exam(leakage_checks_passed=False))
    assert not can_promote_research(exam(final_holdout_eligible=False))

def test_approval_cannot_be_historical_or_role_spoofed():
    p = proposal()
    with pytest.raises(ValidationError):
        approval(p, mode="HISTORICAL")
    with pytest.raises(ValidationError):
        approval(p, actor_role="STUDENT")

def test_contracts_reject_naive_datetimes():
    with pytest.raises(ValidationError):
        proposal(created_at=datetime(2026, 10, 25, 10))

def test_missing_guardian_or_assessment_fails_closed():
    p = proposal()
    a, g = assessed_and_guarded(p)
    assert not research_execution_authorised(p, a, None)
    assert not research_execution_authorised(p, None, g)
    assert not research_execution_authorised(p, None, None)

def test_mismatched_guardian_or_expired_proposal_fails_closed():
    p = proposal()
    a, g = assessed_and_guarded(p)
    assert not guardian_allows(p, a, g.model_copy(update={"proposal_sha256": SHA_A}))
    late_guardian = g.model_copy(update={"decided_at": p.expires_at})
    assert not guardian_allows(p, a, late_guardian)
