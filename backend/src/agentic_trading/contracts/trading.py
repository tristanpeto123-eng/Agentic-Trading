"""Trade proposal and Guardian-review contracts, with revision binding."""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from agentic_trading.contracts.common import FrozenModel, Sha256, require_utc

class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"

class Decision(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"

class TradeProposal(FrozenModel):
    schema_version: Literal["trade_proposal.v1"] = "trade_proposal.v1"
    proposal_id: UUID
    revision: int = Field(ge=1)
    student_id: UUID
    strategy_version: str = Field(min_length=1)
    model_sha256: Sha256
    instrument: str = Field(min_length=1)
    direction: Direction
    entry_reference: Decimal = Field(gt=0)
    stop_price: Decimal = Field(gt=0)
    target_price: Decimal = Field(gt=0)
    tactic_id: str = Field(min_length=1)
    thesis: str = Field(min_length=1)
    invalidation: str = Field(min_length=1)
    observed_data_available_at: datetime
    created_at: datetime
    expires_at: datetime
    content_sha256: Sha256

    @field_validator("observed_data_available_at", "created_at", "expires_at")
    @classmethod
    def utc_only(cls, v: datetime) -> datetime:
        return require_utc(v)

    @model_validator(mode="after")
    def validate_prices_and_time(self):
        if not self.observed_data_available_at <= self.created_at < self.expires_at:
            raise ValueError("proposal cannot use future data or have expired timing")
        if self.direction == Direction.LONG and not (self.stop_price < self.entry_reference < self.target_price):
            raise ValueError("LONG requires stop < entry reference < target")
        if self.direction == Direction.SHORT and not (self.target_price < self.entry_reference < self.stop_price):
            raise ValueError("SHORT requires target < entry reference < stop")
        return self

class TradeAssessment(FrozenModel):
    schema_version: Literal["trade_assessment.v1"] = "trade_assessment.v1"
    proposal_id: UUID
    proposal_revision: int = Field(ge=1)
    proposal_sha256: Sha256
    scout_b_model_sha256: Sha256
    expected_net_r: Decimal
    assessed_at: datetime

    @field_validator("assessed_at")
    @classmethod
    def utc_only(cls, v: datetime) -> datetime:
        return require_utc(v)

class GuardianDecision(FrozenModel):
    schema_version: Literal["guardian_decision.v1"] = "guardian_decision.v1"
    proposal_id: UUID
    proposal_revision: int = Field(ge=1)
    proposal_sha256: Sha256
    decision: Decision
    reasons: tuple[str, ...] = Field(min_length=1)
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def utc_only(cls, v: datetime) -> datetime:
        return require_utc(v)
