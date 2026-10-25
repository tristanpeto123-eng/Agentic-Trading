"""Independent research exam evidence; trading permission is always separate."""
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import Field
from agentic_trading.contracts.common import EvidenceKind, FrozenModel, Sha256

class ResearchExamEvidence(FrozenModel):
    schema_version: Literal["research_exam.v1"] = "research_exam.v1"
    exam_id: UUID
    student_id: UUID
    challenger_model_sha256: Sha256
    champion_model_sha256: Sha256
    dataset_sha256: Sha256
    evidence_kind: EvidenceKind
    closed_trades: int = Field(ge=0)
    profit_factor: Decimal = Field(ge=0)
    max_drawdown_fraction: Decimal = Field(ge=0, le=1)
    net_pnl: Decimal
    champion_outperformed: bool
    integrity_passed: bool
    leakage_checks_passed: bool
    independently_reproduced: bool
    final_holdout_eligible: bool
