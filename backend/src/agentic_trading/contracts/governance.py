"""Exact-scope CEO approvals. Design schemas, not operational permissions database."""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from agentic_trading.contracts.common import FrozenModel, Sha256, require_utc

class AuthorizationMode(StrEnum):
    HISTORICAL = "HISTORICAL"
    PAPER = "PAPER"
    LIVE = "LIVE"

class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class CEOApproval(FrozenModel):
    schema_version: Literal["ceo_approval.v1"] = "ceo_approval.v1"
    approval_id: UUID
    actor_id: UUID
    actor_role: Literal["CEO"] = "CEO"
    decision: ApprovalDecision
    student_id: UUID
    model_sha256: Sha256
    strategy_version: str = Field(min_length=1)
    mode: AuthorizationMode
    instrument: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    capital_limit: Decimal = Field(gt=0)
    per_trade_risk_limit: Decimal = Field(gt=0, le=1)
    leverage_limit: Decimal = Field(gt=0)
    approved_at: datetime
    expires_at: datetime

    @field_validator("approved_at", "expires_at")
    @classmethod
    def utc_only(cls, v: datetime) -> datetime:
        return require_utc(v)

    @model_validator(mode="after")
    def valid_window_and_scope(self):
        if self.approved_at >= self.expires_at:
            raise ValueError("approval must have a finite future expiry")
        if self.mode == AuthorizationMode.HISTORICAL:
            raise ValueError("CEO approval records are for paper or live permissions")
        return self
