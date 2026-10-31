"""CEO-only, read-only M15 decision traces from the existing S4 research pipeline.

Input candles are supplied by the caller and ALWAYS unverified. This runs actual
Scout A / Strategist / Scout B (without an independent fitted Scout B model) /
Guardian gating in research_decision; it is NOT neural inference or an order path.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from agentic_trading.contracts.common import EvidenceKind
from agentic_trading.intelligence import (
    SignalCandle, MarketWindow, research_decision, trace_digest,
)

MAX_WINDOW = 192
MAX_EVALUATIONS = 24


class TraceBatchInput(BaseModel):
    student_id: UUID
    price_basis: Literal["bid", "ask", "mid"] = "mid"
    candles: list[SignalCandle] = Field(min_length=1, max_length=360)
    first_index: int = Field(ge=0)
    last_index: int = Field(ge=0)

    @model_validator(mode="after")
    def bounded(self):
        if self.first_index > self.last_index or self.last_index >= len(self.candles):
            raise ValueError("Decision interval lies outside supplied candles")
        if self.last_index - self.first_index + 1 > MAX_EVALUATIONS:
            raise ValueError("Maximum 24 decision inspections per request")
        if self.candles[-1].available_at > datetime.now(timezone.utc):
            raise ValueError("Future or incomplete M15 candles are not accepted")
        if any(b.open_time <= a.open_time for a, b in zip(self.candles, self.candles[1:])):
            raise ValueError("Candle timestamps must increase strictly, without duplicates")
        return self


def inspect_trace_batch(payload: TraceBatchInput, *, permitted_skills: set[str]) -> dict:
    """No database writes; no authenticated model inference; no paper/live routes.

    All output is research-only. A candidate without trained Scout B + Guardian
    cannot be called a trade decision. Only *actual* S4 engine output is shown.
    """
    observations = []
    for index in range(payload.first_index, payload.last_index + 1):
        selected = payload.candles[max(0, index - MAX_WINDOW + 1):index + 1]
        at = selected[-1].available_at
        if any(b.open_time - a.open_time != timedelta(minutes=15)
               for a, b in zip(selected, selected[1:])):
            observations.append({
                "index": index, "observed_at": at.isoformat().replace("+00:00", "Z"),
                "state": "DATA_GAP", "decision": "NO_TRADE",
                "reason": "NON_CONTIGUOUS_M15_HISTORY",
                "regime": None, "candidate": None,
                "scout_b": "NOT_EVALUATED", "guardian": "NOT_EVALUATED",
                "trace_sha256": None,
            })
            continue
        canonical = json.dumps([bar.model_dump(mode="json") for bar in selected],
                               sort_keys=True, separators=(",", ":")).encode("utf-8")
        window = MarketWindow(
            instrument="XAUUSD",
            source_sha256=sha256(canonical).hexdigest(),
            evidence_kind=EvidenceKind.HISTORICAL_UNVERIFIED,
            price_basis=payload.price_basis,
            as_of=at,
            candles=tuple(selected),
        )
        trace = research_decision(window, payload.student_id, model=None)
        if trace.trace_sha256 != trace_digest(trace):
            raise ValueError("Decision trace digest failed integrity validation")
        proposed = trace.candidate
        tactic_name = ({
            "TREND_CONTINUATION": "trend",
            "BREAKOUT": "breakout",
            "RANGE_REVERSION": "range",
        }.get(proposed.tactic_id) if proposed else None)
        in_plan = not proposed or tactic_name in permitted_skills
        reason = "OUTSIDE_STUDENT_LEARNING_PLAN" if not in_plan else trace.reason
        observations.append({
            "index": index, "observed_at": at.isoformat().replace("+00:00", "Z"),
            "state": "UNQUALIFIED_RESEARCH_TRACE",
            "decision": "NO_TRADE", "reason": reason,
            "regime": {
                "market": trace.regime.market.value,
                "volatility": trace.regime.volatility.value,
                "confidence": str(trace.regime.confidence),
                "atr": str(trace.regime.atr),
                "efficiency": str(trace.regime.efficiency),
                "h1_direction": trace.regime.h1_direction,
                "h4_direction": trace.regime.h4_direction,
                "reasons": list(trace.regime.reasons),
            },
            "candidate": ({
                "direction": proposed.direction.value,
                "tactic": proposed.tactic_id,
                "entry_reference": str(proposed.entry_reference),
                "stop_price": str(proposed.stop_price),
                "target_price": str(proposed.target_price),
                "proposed_at": proposed.observed_data_available_at.isoformat().replace("+00:00", "Z"),
                "plan_permitted": in_plan,
                "content_sha256": proposed.content_sha256,
                "policy_sha256": proposed.model_sha256,
            } if proposed else None),
            "scout_b": "NOT_TRAINED_OR_BOUND" if proposed else "NOT_REACHED",
            "guardian": "NOT_EVALUATED",
            "trace_sha256": trace.trace_sha256,
        })
    return {
        "schema": "research_decision_trace.v1",
        "engine": "EXISTING_S4_DETERMINISTIC_REFERENCE_PIPELINE",
        "student_id": str(payload.student_id),
        "price_basis": payload.price_basis,
        "source_verified": False,
        "independently_trained_scout_b": False,
        "neural_checkpoint_inference_enabled": False,
        "research_only": True,
        "simulated_orders_created": 0,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "observations": observations,
        "note": "This is actual deterministic Scout A / Strategist research logic. Without an independently trained Scout B there can be no Guardian-approved intent; no orders are created.",
    }
