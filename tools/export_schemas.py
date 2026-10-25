"""Export contract JSON schemas for web clients. Run from installed backend environment."""
import json
from pathlib import Path

from agentic_trading.contracts import (
    EventEnvelope, TradeProposal, TradeAssessment, GuardianDecision,
    CEOApproval, ResearchExamEvidence,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "contracts" / "json-schema"

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for model in (EventEnvelope, TradeProposal, TradeAssessment, GuardianDecision, CEOApproval, ResearchExamEvidence):
        (OUTPUT / f"{model.__name__}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
        )

if __name__ == "__main__":
    main()
