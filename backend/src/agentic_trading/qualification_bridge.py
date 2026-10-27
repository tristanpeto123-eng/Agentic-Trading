"""Research-only qualification bridge for strictly ingested XAUUSD M15 CSV.

Provenance flags are independent attestations, never inferred from CSV metadata.
No broker calls, agent promotion, or trading activation.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from agentic_trading.data_engine import ingest_csv
from agentic_trading.qualification import assess_candles


def inspect_historical_csv(
    csv_content: str,
    acquired_at: datetime,
    *,
    provenance_verified: bool = False,
    rights_verified: bool = False,
    minimum_rows: int = 1000,
) -> dict:
    candles, quality, canonical = ingest_csv(csv_content, acquired_at)
    assessment = assess_candles(
        candles,
        provenance_verified=provenance_verified,
        rights_verified=rights_verified,
        minimum_rows=minimum_rows,
    )
    warnings = list(quality["warnings"])
    # Quality warnings cannot be silently ignored to claim research readiness.
    issues = list(assessment.issues)
    if quality["gap_count"]:
        issues.append("unreviewed timestamp gaps")
    if quality["large_move_alerts"]:
        issues.append("unreviewed extreme price moves")
    if quality["stale_quote_run_alerts"]:
        issues.append("unreviewed stale quote runs")
    if quality["calendar_days"] < 365:
        issues.append("less than 365 days of historical coverage")
    if not all(c.volume is not None for c in candles):
        warnings.append("Missing volume: volume-dependent studies are unsupported.")
    return {
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "source_sha256": sha256(csv_content.encode("utf-8")).hexdigest(),
        "canonical_sha256": sha256(canonical).hexdigest(),
        "qualification": {
            **assessment.__dict__,
            "issues": issues,
            "data_screen_passed": assessment.research_eligible and not issues,
            "research_eligible": False,
            "independent_source_verification_required": True,
            "paper_eligible": False,
            "live_eligible": False,
        },
        "quality": quality,
        "warnings": warnings,
        "backtest_performed": False,
        "agent_qualified": False,
        "registrar_approved": False,
        "ceo_approved": False,
    }
