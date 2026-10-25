"""Fail-closed design policy checks. No trading or broker endpoints exist."""
from datetime import datetime
from decimal import Decimal

from agentic_trading.contracts.academy import ResearchExamEvidence
from agentic_trading.contracts.common import EvidenceKind, require_utc
from agentic_trading.contracts.governance import CEOApproval, ApprovalDecision, AuthorizationMode
from agentic_trading.contracts.trading import Decision, GuardianDecision, TradeAssessment, TradeProposal

def matches_assessment(proposal: TradeProposal, assessment: TradeAssessment | None) -> bool:
    if assessment is None:
        return False
    return (
        proposal.proposal_id == assessment.proposal_id
        and proposal.revision == assessment.proposal_revision
        and proposal.content_sha256 == assessment.proposal_sha256
        and proposal.created_at <= assessment.assessed_at < proposal.expires_at
    )

def guardian_allows(proposal: TradeProposal, assessment: TradeAssessment | None, guardian: GuardianDecision | None) -> bool:
    if guardian is None or assessment is None:
        return False
    return (
        matches_assessment(proposal, assessment)
        and guardian.decision == Decision.APPROVED
        and guardian.proposal_id == proposal.proposal_id
        and guardian.proposal_revision == proposal.revision
        and guardian.proposal_sha256 == proposal.content_sha256
        and guardian.decided_at >= assessment.assessed_at
        and guardian.decided_at < proposal.expires_at
    )

def approval_allows(approval: CEOApproval | None, proposal: TradeProposal, mode: AuthorizationMode, account_id: str, decision_at: datetime) -> bool:
    require_utc(decision_at)
    return bool(
        approval is not None
        and approval.decision == ApprovalDecision.APPROVED
        and approval.mode == mode
        and approval.account_id == account_id
        and approval.student_id == proposal.student_id
        and approval.instrument == proposal.instrument
        and approval.model_sha256 == proposal.model_sha256
        and approval.strategy_version == proposal.strategy_version
        and approval.approved_at <= decision_at < approval.expires_at
    )

def research_execution_authorised(proposal: TradeProposal, assessment: TradeAssessment | None, guardian: GuardianDecision | None) -> bool:
    """Historical simulator gate only. Paper/live execution intentionally absent."""
    return guardian_allows(proposal, assessment, guardian)

def can_promote_research(evidence: ResearchExamEvidence) -> bool:
    """Necessary numeric/integrity checks; Registrar will later check trial selection and eligibility."""
    return (
        evidence.evidence_kind == EvidenceKind.HISTORICAL_VERIFIED
        and evidence.closed_trades >= 100
        and evidence.profit_factor >= Decimal("1.20")
        and evidence.max_drawdown_fraction <= Decimal("0.15")
        and evidence.net_pnl > 0
        and evidence.champion_outperformed
        and evidence.integrity_passed
        and evidence.leakage_checks_passed
        and evidence.independently_reproduced
        and evidence.final_holdout_eligible
    )
