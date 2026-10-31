"""Bounded, deterministic five-batch *candidate* policy updates (research only).

This updates only per-student skill-selection scores. It never edits the skill
catalog, trains on validation/holdout episodes, promotes a model, persists an
active policy, or calls a broker. All inputs are explicit, closed TRAIN trades
with net returns AFTER spread, slippage and fees. Integration with Academy
worker/persistence and independent validation remains a separate release gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from hashlib import sha256
from typing import Mapping, Sequence
import json


class PolicyResearchError(ValueError):
    """Fail-closed invalid, leaked or mixed-student research evidence."""


@dataclass(frozen=True)
class ClosedTrade:
    trade_id: str
    skill_id: str
    net_r: Decimal
    closed_at: datetime
    available_at: datetime
    partition: str = "train"
    origin: str = "historical_quarantined"


@dataclass(frozen=True)
class ClosedBatch:
    batch_id: str
    student_id: str
    market: str
    completed_at: datetime
    trades: tuple[ClosedTrade, ...]


def _utc(value: datetime, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise PolicyResearchError(f"{label} must be timezone-aware UTC")


def _decimal(value: object, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise PolicyResearchError(f"{label} must be numeric") from exc
    if not number.is_finite():
        raise PolicyResearchError(f"{label} must be finite")
    return number


def _fingerprint(data: dict) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def propose_five_batch_policy(
    *,
    student_id: str,
    market: str,
    as_of: datetime,
    skill_catalog_sha256: str,
    allowed_skills: Sequence[str],
    incumbent_scores: Mapping[str, object],
    incumbent_version: int,
    batches: Sequence[ClosedBatch],
) -> dict:
    """Prepare one immutable five-batch update; never automatically activate it.

    Scores are independent selection preferences in [0,1], NOT probabilities,
    agent qualification, trading signals, or an order strategy. At least three
    closed after-cost TRAIN trades are required before changing any skill's
    candidate score. The damping factor (20%) limits reaction to small samples.

    A separate independent validation/CEO decision must govern accepting or
    rolling back any candidate. No side effects or global state are modified.
    """
    _utc(as_of, "as_of")
    if not student_id or not market or not isinstance(incumbent_version, int) or incumbent_version < 1:
        raise PolicyResearchError("valid student, market and incumbent version are required")
    if (len(skill_catalog_sha256) != 64
            or any(char not in "0123456789abcdef" for char in skill_catalog_sha256)):
        raise PolicyResearchError("invalid frozen skill catalog checksum")
    allowed = tuple(allowed_skills)
    if not allowed or any(not isinstance(s, str) or not s.strip() for s in allowed) or len(set(allowed)) != len(allowed):
        raise PolicyResearchError("skill catalog must contain unique nonempty identifiers")
    if set(incumbent_scores) != set(allowed):
        raise PolicyResearchError("candidate must preserve the frozen skill catalog exactly")
    current = {skill: _decimal(incumbent_scores[skill], f"incumbent score {skill}") for skill in allowed}
    if any(score < 0 or score > 1 for score in current.values()):
        raise PolicyResearchError("selection score outside [0,1]")
    if len(batches) != 5:
        raise PolicyResearchError("exactly five distinct completed batches are required")

    batch_ids: set[str] = set()
    trade_ids: set[str] = set()
    grouped: dict[str, list[Decimal]] = {skill: [] for skill in allowed}
    batch_manifest: list[dict] = []
    last_batch_time: datetime | None = None

    for batch in batches:
        _utc(batch.completed_at, "completed_at")
        if (not batch.batch_id or batch.batch_id in batch_ids
                or batch.student_id != student_id or batch.market != market
                or batch.completed_at > as_of):
            raise PolicyResearchError("duplicate, future or cross-student batch")
        if last_batch_time is not None and batch.completed_at <= last_batch_time:
            raise PolicyResearchError("batch completion times must strictly increase")
        if not batch.trades:
            raise PolicyResearchError("empty batch cannot advance learning cadence")
        batch_ids.add(batch.batch_id)
        last_batch_time = batch.completed_at
        entries: list[dict] = []
        for trade in batch.trades:
            _utc(trade.closed_at, "closed_at")
            _utc(trade.available_at, "available_at")
            if (not trade.trade_id or trade.trade_id in trade_ids
                    or trade.skill_id not in current or trade.partition != "train"
                    or trade.origin not in ("synthetic_fixture", "historical_quarantined")
                    or trade.closed_at > trade.available_at
                    or trade.available_at > batch.completed_at or trade.available_at > as_of):
                raise PolicyResearchError("invalid, future, holdout or duplicate trade")
            net_r = _decimal(trade.net_r, "after-cost net_r")
            trade_ids.add(trade.trade_id)
            grouped[trade.skill_id].append(net_r)
            entries.append({
                "trade_id": trade.trade_id, "skill_id": trade.skill_id,
                "net_r": str(net_r), "closed_at": trade.closed_at.isoformat(),
                "available_at": trade.available_at.isoformat(),
                "partition": trade.partition, "origin": trade.origin,
            })
        batch_manifest.append({
            "batch_id": batch.batch_id, "completed_at": batch.completed_at.isoformat(),
            "trades": entries,
        })

    quant = Decimal("0.000001")
    revised = {}
    evidence = {}
    for skill in allowed:
        values = grouped[skill]
        previous = current[skill]
        if len(values) >= 3:
            # Wins and losses are magnitude-weighted by realised, AFTER-COST R.
            mean_r = sum(values) / Decimal(len(values))
            target = max(Decimal(0), min(Decimal(1), (mean_r + Decimal(1)) / Decimal(2)))
            proposed = Decimal("0.8") * previous + Decimal("0.2") * target
        else:
            proposed = previous
        revised[skill] = str(proposed.quantize(quant, rounding=ROUND_HALF_EVEN))
        evidence[skill] = {"train_trades": len(values), "changed": len(values) >= 3}

    record = {
        "schema": "research_policy_candidate.v1",
        "student_id": student_id, "market": market,
        "skill_catalog_sha256": skill_catalog_sha256,
        "from_version": incumbent_version, "candidate_version": incumbent_version + 1,
        "as_of": as_of.isoformat(),
        "previous_scores": {s: str(current[s].quantize(quant, rounding=ROUND_HALF_EVEN)) for s in allowed},
        "candidate_scores": revised,
        "closed_train_trade_count": len(trade_ids),
        "completed_batch_count": len(batch_ids),
        "batch_manifest_sha256": _fingerprint({"batches": batch_manifest}),
        "skill_evidence": evidence,
        "status": "awaiting_independent_validation",
        "research_only": True, "qualified": False,
        "paper_trading_enabled": False, "live_trading_enabled": False,
        "applied_to_student": False,
    }
    return {**record, "candidate_sha256": _fingerprint(record)}
