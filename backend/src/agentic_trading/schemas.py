"""Sprint 1 API validation - plans are targets, NOT earned mastery."""
from datetime import datetime
from enum import StrEnum
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LearningMode(StrEnum):
    AUTONOMOUS = "autonomous"
    DIRECTED = "directed"


class Market(StrEnum):
    XAUUSD = "XAUUSD"
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    US500 = "US500"
    NAS100 = "NAS100"
    BTCUSD = "BTCUSD"


class Skill(StrEnum):
    TREND = "trend"
    BREAKOUT = "breakout"
    RANGE = "range"
    SCALPING = "scalping"
    SWING = "swing"
    RISK_MANAGEMENT = "risk_management"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1)


class LearningInput(BaseModel):
    mode: LearningMode = LearningMode.AUTONOMOUS
    markets: list[Market] = Field(default_factory=list, max_length=6)
    skills: list[Skill] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def check_scope(self):
        if len(set(self.markets)) != len(self.markets) or len(set(self.skills)) != len(self.skills):
            raise ValueError("Duplicate learning targets are not allowed")
        if self.mode == LearningMode.DIRECTED and (not self.markets or not self.skills):
            raise ValueError("Directed learning needs at least one market and one skill")
        if self.mode == LearningMode.AUTONOMOUS and (self.markets or self.skills):
            raise ValueError("Autonomous learning cannot have directed targets")
        return self


class CreateStudent(LearningInput):
    name: str = Field(min_length=2, max_length=40)

    @field_validator("name")
    @classmethod
    def normalise_name(cls, name: str) -> str:
        name = " ".join(unicodedata.normalize("NFKC", name).split())
        if not (2 <= len(name) <= 40) or not any(c.isalpha() for c in name):
            raise ValueError("Use a 2-40 character name containing at least one letter")
        if not all(c.isalnum() or c in " -_" for c in name):
            raise ValueError("Name can contain letters, numbers, spaces, dashes and underscores")
        return name


class RenameStudent(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def normalise_name(cls, name: str) -> str:
        return CreateStudent.normalise_name(name)


class ChangeDirection(LearningInput):
    reason: str = Field(default="CEO updated learning direction", min_length=3, max_length=200)


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    version: int
    mode: LearningMode
    markets: list[Market]
    skills: list[Skill]
    reason: str
    created_at: datetime


class StudentResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    learning_plan: PlanResponse
    plan_history: list[PlanResponse] | None = None
    training_active: bool = False
    qualification: str = "unqualified"


def name_key(name: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", name).strip()).casefold()
