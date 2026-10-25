"""Schema-generation smoke test; persisted snapshot verification follows when schemas are published."""
from agentic_trading.contracts import (
    EventEnvelope, TradeProposal, TradeAssessment, GuardianDecision,
    CEOApproval, ResearchExamEvidence,
)

def test_contracts_export_json_schema():
    for cls in (EventEnvelope, TradeProposal, TradeAssessment, GuardianDecision, CEOApproval, ResearchExamEvidence):
        schema = cls.model_json_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert schema["title"] == cls.__name__
