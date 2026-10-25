"""Cross-service event envelope, provenance and point-in-time checks."""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

class EvidenceKind(StrEnum):
    HISTORICAL_VERIFIED = "historical_verified"
    HISTORICAL_UNVERIFIED = "historical_unverified"
    SYNTHETIC = "synthetic"
    COUNTERFACTUAL = "counterfactual"
    PAPER_FORWARD = "paper_forward"
    LIVE_EXECUTED = "live_executed"

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must be timezone-aware and UTC")
    return value

class Provenance(FrozenModel):
    evidence_kind: EvidenceKind
    source_id: str = Field(min_length=1)
    source_sha256: Sha256

class EventEnvelope(FrozenModel):
    """Shared metadata. Consumers must still validate payload type and signature."""
    schema_version: str = Field(pattern=r"^v1$")
    event_type: str = Field(min_length=1)
    event_id: UUID
    correlation_id: UUID
    run_id: UUID | None = None
    student_id: UUID | None = None
    producer: str = Field(min_length=1)
    model_version: str | None = None
    occurred_at: datetime
    available_at: datetime
    payload_sha256: Sha256
    provenance: Provenance

    @field_validator("occurred_at", "available_at")
    @classmethod
    def utc_only(cls, v: datetime) -> datetime:
        return require_utc(v)

    @model_validator(mode="after")
    def availability_not_before_event(self):
        if self.available_at < self.occurred_at:
            raise ValueError("available_at precedes occurred_at")
        return self

    def assert_visible_at(self, decision_at: datetime) -> None:
        require_utc(decision_at)
        if self.available_at > decision_at:
            raise ValueError("future information is not visible at decision time")
