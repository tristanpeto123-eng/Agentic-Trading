"""Fail-closed model-to-paper readiness screening; no execution side effects."""
from copy import deepcopy

import pytest

from agentic_trading.demo_qualification import (
    DemoQualificationError, assess_demo_candidate,
)


def full_claimed_evidence():
    model = {
        key: letter * 64
        for key, letter in (
            ("model_sha256", "a"), ("dataset_sha256", "b"),
            ("skill_catalog_sha256", "c"), ("signals_sha256", "d"),
            ("configuration_sha256", "e"),
        )
    }
    model.update({
        "checkpoint_generated_signals": True,
        "independent_reproduction": True,
        "holdout_was_sealed": True,
        "no_lookahead_verified": True,
        "private_data_use_permitted": True,
        "execution_costs_verified": True,
    })
    return {
        "model": model,
        "holdout": {
            "closed_trades": 200, "net_pnl_usd": "48",
            "profit_factor": "1.4", "maximum_drawdown_fraction": "0.04",
            "no_trade_baseline_net_usd": "0",
            "double_cost_net_pnl_usd": "20", "unresolved_trades": 0,
        },
        "walk_forward_folds": [{"net_pnl_usd": "5"}] * 3,
        "operations": {
            "paper_account_pinned": True, "paper_keys_only": True,
            "live_disabled": True, "private_backup_restored": True,
            "paper_reconciliation_verified": True,
            "kill_switch_verified": True, "ceo_paper_scope_signed": True,
        },
    }


def test_empty_and_losing_cases_fail_closed():
    missing = assess_demo_candidate({})
    assert missing["outcome"] == "BLOCKED"
    assert not missing["paper_orders_enabled"]
    assert not missing["live_orders_enabled"]
    assert not missing["paper_activation_authorised"]

    case = full_claimed_evidence()
    case["holdout"]["net_pnl_usd"] = "-184.078"
    case["holdout"]["profit_factor"] = "0.5202"
    case["holdout"]["maximum_drawdown_fraction"] = "0.1855"
    case["holdout"]["double_cost_net_pnl_usd"] = "-308.278"
    case["walk_forward_folds"] = [{"net_pnl_usd": "-1"}] * 3
    report = assess_demo_candidate(case)
    assert not report["model_evaluation_screen_passed"]
    assert report["outcome"] == "BLOCKED"
    assert not report["checks"]["positive_after_cost_vs_cash"]


def test_no_broker_authority_even_with_perfect_claims():
    report = assess_demo_candidate(full_claimed_evidence())
    assert report["model_evaluation_screen_passed"]
    assert report["operational_review_evidence_complete"]
    assert report["paper_review_possible"]
    assert report["outcome"] == "EVIDENCE_COMPLETE_REVIEW_ONLY"
    assert not report["paper_orders_enabled"]
    assert not report["live_orders_enabled"]
    assert not report["paper_activation_authorised"]
    assert not report["registrar_qualified"]


def test_missing_execution_proof_or_ceo_prevents_review():
    fixture = full_claimed_evidence()
    fixture["model"]["checkpoint_generated_signals"] = False
    assert not assess_demo_candidate(fixture)["paper_review_possible"]
    fixture = full_claimed_evidence()
    fixture["operations"]["ceo_paper_scope_signed"] = False
    assert not assess_demo_candidate(fixture)["paper_review_possible"]


@pytest.mark.parametrize("value", ["NaN", "Infinity", True, {}, "not-number"])
def test_untrusted_numerical_fields_cannot_bypass_gate(value):
    fixture = full_claimed_evidence()
    fixture["holdout"]["net_pnl_usd"] = value
    with pytest.raises(DemoQualificationError):
        assess_demo_candidate(fixture)


def test_missing_folds_and_missing_hash_fail_closed():
    fixture = full_claimed_evidence()
    fixture["walk_forward_folds"] = fixture["walk_forward_folds"][:2]
    fixture["model"]["model_sha256"] = "not-a-sha"
    result = assess_demo_candidate(fixture)
    assert not result["checks"]["model_and_inputs_pinned"]
    assert not result["checks"]["three_positive_independent_development_folds"]
    assert not result["paper_review_possible"]


def test_integrity_fingerprint_stable_and_changes_with_data():
    original = full_claimed_evidence()
    first = assess_demo_candidate(original)["evidence_sha256"]
    assert first == assess_demo_candidate(deepcopy(original))["evidence_sha256"]
    original["holdout"]["net_pnl_usd"] = "47"
    assert first != assess_demo_candidate(original)["evidence_sha256"]
