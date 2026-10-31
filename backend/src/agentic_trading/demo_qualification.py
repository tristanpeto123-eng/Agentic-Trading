"""Offline paper-*candidate* validation gate; never broker execution approval.

A completed research evaluation can be reviewed for a bounded paper pilot even
without a commercial data-vendor contract *if* its specific private data usage
is permitted. Claiming 'demo' does not prove provider rights or performance.

The caller cannot change any trading setting, student, model or broker account.
All positive metrics must be backed by separately reproduced pinned-model
signals and an actual isolated holdout. This module stores no mutable state.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Mapping


class DemoQualificationError(ValueError):
    pass


def _number(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise DemoQualificationError(f"{label} cannot be boolean")
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DemoQualificationError(f"{label} must be numeric") from exc
    if not val.is_finite():
        raise DemoQualificationError(f"{label} must be finite")
    return val


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("utf-8")).hexdigest()


def assess_demo_candidate(evidence: Mapping) -> dict:
    """Descriptive eligibility for *review*, never automatic paper activation.

    All booleans are independently verifiable proof assertions from the
    examiner process, not authorisations to let a model place orders.
    Missing assertions or measurements fail closed. A profitable-looking
    backtest cannot substitute for provenance, isolation or execution evidence.
    """
    if not isinstance(evidence, Mapping):
        raise DemoQualificationError("Expected a report mapping")
    model = evidence.get("model", {})
    validation = evidence.get("holdout", {})
    folds = evidence.get("walk_forward_folds", ())
    operation = evidence.get("operations", {})
    if not all(isinstance(v, Mapping) for v in (model, validation, operation)):
        raise DemoQualificationError("Invalid evidence sections")
    if not isinstance(folds, (list, tuple)):
        raise DemoQualificationError("Walk-forward folds must be a sequence")
    hashes = ("model_sha256", "dataset_sha256", "skill_catalog_sha256",
              "signals_sha256", "configuration_sha256")
    pinned = all(isinstance(model.get(k), str)
                 and len(model[k]) == 64
                 and all(ch in "0123456789abcdef" for ch in model[k])
                 for k in hashes)
    model_checks = {
        "model_and_inputs_pinned": pinned,
        "signals_generated_by_frozen_model": model.get("checkpoint_generated_signals") is True,
        "independent_reproduction": model.get("independent_reproduction") is True,
        "holdout_untouched_during_selection": model.get("holdout_was_sealed") is True,
        "point_in_time_features_verified": model.get("no_lookahead_verified") is True,
        "private_source_use_authorised": model.get("private_data_use_permitted") is True,
        "execution_costs_and_fills_verified": model.get("execution_costs_verified") is True,
    }
    required = ("closed_trades", "net_pnl_usd", "profit_factor",
                "maximum_drawdown_fraction", "no_trade_baseline_net_usd",
                "double_cost_net_pnl_usd", "unresolved_trades")
    numbers = {}
    for field in required:
        if field in validation:
            numbers[field] = _number(validation[field], field)
    complete = len(numbers) == len(required)
    metric_checks = {
        "complete_holdout_metrics": complete,
        "at_least_100_closed_trades": complete and numbers["closed_trades"] >= 100,
        "positive_after_cost_vs_cash": (complete and numbers["net_pnl_usd"] > 0
                                        and numbers["net_pnl_usd"] > numbers["no_trade_baseline_net_usd"]),
        "profit_factor_at_least_1_20": complete and numbers["profit_factor"] >= Decimal("1.20"),
        "drawdown_at_most_15pct": complete and
            0 <= numbers["maximum_drawdown_fraction"] <= Decimal("0.15"),
        "double_cost_still_positive": complete and numbers["double_cost_net_pnl_usd"] > 0,
        "no_unresolved_exposures": complete and numbers["unresolved_trades"] == 0,
    }
    valid_folds = len(folds) >= 3
    for fold in folds:
        if not isinstance(fold, Mapping) or "net_pnl_usd" not in fold:
            valid_folds = False
            break
        valid_folds = valid_folds and _number(fold["net_pnl_usd"], "fold P&L") > 0
    metric_checks["three_positive_independent_development_folds"] = valid_folds
    operation_checks = {
        "paper_account_identity_bound": operation.get("paper_account_pinned") is True,
        "paper_only_credentials": operation.get("paper_keys_only") is True,
        "live_execution_disabled": operation.get("live_disabled") is True,
        "persistent_recovery_drill": operation.get("private_backup_restored") is True,
        "order_reconciliation_tested": operation.get("paper_reconciliation_verified") is True,
        "guardian_and_emergency_stop_tested": operation.get("kill_switch_verified") is True,
        "signed_owner_scope": operation.get("ceo_paper_scope_signed") is True,
    }
    checks = {**model_checks, **metric_checks, **operation_checks}
    evidence_sha = _digest({"model": model, "holdout": validation,
                            "walk_forward_folds": list(folds), "operations": operation})
    all_pass = all(checks.values())
    return {
        "schema": "bounded_demo_candidate_review.v1",
        "evidence_sha256": evidence_sha,
        "checks": checks,
        "model_evaluation_screen_passed": all(model_checks.values()) and all(metric_checks.values()),
        "operational_review_evidence_complete": all(operation_checks.values()),
        "paper_review_possible": all_pass,
        "paper_orders_enabled": False,
        "live_orders_enabled": False,
        "paper_activation_authorised": False,
        "registrar_qualified": False,
        "outcome": "EVIDENCE_COMPLETE_REVIEW_ONLY" if all_pass else "BLOCKED",
        "note": "Even complete evidence does not activate broker orders. A separate, explicit CEO release and implemented guarded paper execution workflow are required.",
    }
