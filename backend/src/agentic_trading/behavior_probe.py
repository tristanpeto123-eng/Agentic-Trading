"""Deterministic policy-action sensitivity on the existing synthetic costed replay.

Instrumentation is observational only: no forced entries, reward bonuses, policy
promotion, broker calls, or modification of the saved Evolution Tower student.
This is not a CFD simulator validation or an out-of-sample qualification exam.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import random
from typing import Sequence

from agentic_trading.evolution_tower import GENES, TowerError, evaluate


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def mutation_behavior_probe(
    genes: Sequence[float], tape: Sequence[float], *,
    seed: int = 20261101, mirrored_pairs: int = 8, sigma: float = 0.06,
) -> dict:
    """Test equal-size plus/minus mutations against one identical toy tape.

    This measures whether mutated weights actually change replay decisions,
    not just whether a chromosome hash changes. All variants are probes, never
    accepted candidate updates, and the tape must not contain sealed holdout.
    """
    original = tuple(genes)
    prices = list(tape)
    if len(original) != GENES or any(not isinstance(g, (int, float)) or
                                    isinstance(g, bool) or not math.isfinite(g) or abs(g) > 3.0
                                    for g in original):
        raise TowerError("invalid bounded research policy")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TowerError("probe seed must be an integer")
    if not isinstance(mirrored_pairs, int) or isinstance(mirrored_pairs, bool) or not (1 <= mirrored_pairs <= 32):
        raise TowerError("probe pairs outside 1..32")
    if not isinstance(sigma, (float, int)) or isinstance(sigma, bool) or not math.isfinite(sigma) or not (0.001 <= sigma <= 0.5):
        raise TowerError("probe sigma outside bounded limits")
    baseline = evaluate(list(original), prices, capture_behavior=True)
    basis = baseline["behavior"]
    rng = random.Random(seed)
    same_decisions = 0
    same_fitness_different_decisions = 0
    different_entries = 0
    inactive_mutants = 0
    signatures = {basis["decision_sha256"]}
    samples = []
    for pair in range(mirrored_pairs):
        noise = tuple(rng.gauss(0, 1) for _ in original)
        for direction in (+1, -1):
            candidate = [max(-3., min(3., g + direction * sigma * n))
                         for g, n in zip(original, noise)]
            replay = evaluate(candidate, prices, capture_behavior=True)
            behavior = replay["behavior"]
            identical = behavior["decision_sha256"] == basis["decision_sha256"]
            same_decisions += int(identical)
            same_fitness_different_decisions += int(
                not identical and replay["fitness"] == baseline["fitness"])
            different_entries += int(behavior["entries"] != basis["entries"])
            inactive_mutants += int(behavior["entries"] == 0)
            signatures.add(behavior["decision_sha256"])
            samples.append({
                "pair": pair + 1, "direction": "+" if direction > 0 else "-",
                "changed_decisions": not identical,
                "entries": behavior["entries"],
                "flat_abstentions": behavior["flat_abstentions"],
                "fitness": replay["fitness"],
            })
    return {
        "schema": "atl_behavior_mutation_probe.v1",
        "data_kind": "caller_supplied_unqualified_research",
        "data_sha256": _digest(prices),
        "initial_weights_sha256": _digest(original),
        "seed": seed, "sigma": float(sigma), "mirrored_pairs": mirrored_pairs,
        "variants_evaluated": 2 * mirrored_pairs,
        "baseline_fitness": baseline["fitness"],
        "baseline_behavior": basis,
        "unchanged_decision_variants": same_decisions,
        "changed_decision_variants": 2 * mirrored_pairs - same_decisions,
        "same_fitness_but_changed_decision_variants": same_fitness_different_decisions,
        "changed_entry_count_variants": different_entries,
        "inactive_mutants": inactive_mutants,
        "unique_decision_signatures_including_baseline": len(signatures),
        "samples": samples,
        "fitness_used_to_select_models": False,
        "research_only": True, "qualified": False,
        "applied_to_student": False,
        "paper_trading_enabled": False, "live_trading_enabled": False,
    }
