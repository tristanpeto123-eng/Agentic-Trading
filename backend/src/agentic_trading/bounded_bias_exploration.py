"""Bounded action-bias exploration for offline research students ONLY.

This tests why output-saturated or overactive Tower policies resist small ES
mutations. It only explores the four final-layer action biases of a copy of
the existing 6->8->4 chromosome, scoring every variant with the unchanged
costed simulator. No model update, broker routing, skill mutation or promotion.

This is NOT a real-market strategy, a qualification exam or a risk-policy fix.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Sequence

from agentic_trading.evolution_tower import GENES, TowerError, evaluate


ACTION_BIASES = ("HOLD", "BUY", "SELL", "CLOSE")
FIXED_SHIFTS = (0.75, 1.5, 2.5)
MAX_ABS_GENE = 3.0


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _safe_weights(values: Sequence[float]) -> tuple[float, ...]:
    weights = tuple(values)
    if (len(weights) != GENES
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) or abs(value) > MAX_ABS_GENE
                   for value in weights)):
        raise TowerError("invalid bounded output-bias research chromosome")
    return weights


def _safe_tape(values: Sequence[float], label: str) -> tuple[float, ...]:
    tape = tuple(values)
    if (not 128 <= len(tape) <= 769
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not math.isfinite(x) or x <= 0 for x in tape)):
        raise TowerError(f"invalid {label} research tape")
    return tape


def explore_action_biases(
    initial_genes: Sequence[float],
    train_tape: Sequence[float],
    diagnostic_tape: Sequence[float],
) -> dict:
    """Compare 24 bounded output-bias variants on TRAIN, then diagnose once.

    The diagnostic tape may not select candidates; it is only evaluated after
    the best training policy is frozen. The best training score can be achieved
    by doing nothing; *never* represent that as profitable trading.
    The caller must supply non-sealed, permitted research data.
    """
    original = _safe_weights(initial_genes)
    train = _safe_tape(train_tape, "train")
    diagnostic = _safe_tape(diagnostic_tape, "diagnostic")
    train_sha, diagnostic_sha = _hash(train), _hash(diagnostic)
    if train_sha == diagnostic_sha:
        raise TowerError("train and diagnostic tapes must differ")

    baseline = evaluate(list(original), list(train), capture_behavior=True)
    selected = original
    best_score = baseline["fitness"]
    best_choice = {"action": None, "shift": 0.0, "train_fitness_improved": False}
    variants = []
    changed_action_sequences = 0
    changed_entry_counts = 0
    inactive_variants = 0

    for action_index, action in enumerate(ACTION_BIASES):
        for amount in FIXED_SHIFTS:
            for sign in (-1, 1):
                offset = 88 + action_index
                proposed = list(original)
                proposed[offset] = max(-MAX_ABS_GENE, min(MAX_ABS_GENE, proposed[offset] + sign * amount))
                frozen = tuple(proposed)
                replay = evaluate(list(frozen), list(train), capture_behavior=True)
                behavior = replay["behavior"]
                different_actions = behavior["decision_sha256"] != baseline["behavior"]["decision_sha256"]
                changed_action_sequences += int(different_actions)
                changed_entry_counts += int(behavior["entries"] != baseline["trades"])
                inactive_variants += int(behavior["entries"] == 0)
                if replay["fitness"] > best_score:
                    best_score = replay["fitness"]
                    selected = frozen
                    best_choice = {"action": action, "shift": float(sign * amount),
                                   "train_fitness_improved": True}
                variants.append({
                    "action": action, "shift": float(sign * amount),
                    "train_fitness": replay["fitness"],
                    "entries": behavior["entries"],
                    "decision_sequence_changed": different_actions,
                    "action_counts": behavior["action_counts"],
                    "risk_breached": replay["risk_breached"],
                })

    # Diagnostic access is ONLY after all 24 training experiments and
    # deterministic train-only selection have completed. It cannot choose the
    # champion or trigger qualification, regardless of observed fitness.
    diagnostic_baseline = evaluate(list(original), list(diagnostic), capture_behavior=True)
    diagnostic_selected = evaluate(list(selected), list(diagnostic), capture_behavior=True)
    best_train = evaluate(list(selected), list(train), capture_behavior=True)
    report = {
        "schema": "atl_bounded_bias_exploration.v1",
        "source_kind": "UNQUALIFIED_RESEARCH_TAPES",
        "train_sha256": train_sha, "diagnostic_sha256": diagnostic_sha,
        "initial_weights_sha256": _hash(original),
        "selected_weights_sha256": _hash(selected),
        "fixed_output_bias_actions": list(ACTION_BIASES),
        "fixed_shift_magnitudes": list(FIXED_SHIFTS),
        "training_evaluations": 26,  # initial + 24 variants + final audit
        "diagnostic_evaluations": 2,
        "baseline_train_fitness": baseline["fitness"],
        "selected_train_fitness": best_train["fitness"],
        "best_train_choice": best_choice,
        "baseline_train_behavior": baseline["behavior"],
        "selected_train_behavior": best_train["behavior"],
        "baseline_diagnostic_fitness": diagnostic_baseline["fitness"],
        "selected_diagnostic_fitness": diagnostic_selected["fitness"],
        "baseline_diagnostic_behavior": diagnostic_baseline["behavior"],
        "selected_diagnostic_behavior": diagnostic_selected["behavior"],
        "mutants_with_changed_action_sequence": changed_action_sequences,
        "mutants_with_changed_entry_count": changed_entry_counts,
        "inactive_variants": inactive_variants,
        "variants": variants,
        "no_trade_is_not_profitability": best_train["trades"] == 0,
        "diagnostic_did_not_select_weights": True,
        "research_only": True,
        "model_applied_to_student": False,
        "qualified": False,
        "paper_trading_enabled": False, "live_trading_enabled": False,
    }
    report["report_sha256"] = _hash(report)
    return report
