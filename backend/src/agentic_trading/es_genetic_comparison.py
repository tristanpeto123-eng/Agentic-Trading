"""Equal-budget ES versus genetic-mutation CONTROL, offline research only.

The genetic-mutation control mirrors the Tower's weight-perturbation idea but
is NOT the full persisted Evolution Tower (which changes toy tapes per generation).
Both optimisers use one immutable training scorer and the same evaluation budget.
A diagnostic scorer is invoked only after both candidates have been frozen.
No candidate is validated, promoted, or connected to any broker.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import math
import random
from typing import Callable, Sequence

from agentic_trading.es_research import ESConfig, ESResearchError, run_es_research


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _score(callback: Callable[[tuple[float, ...]], float], weights: tuple[float, ...]) -> float:
    value = callback(weights)
    if not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value):
        raise ESResearchError("training or diagnostic fitness must be a finite scalar")
    return float(value)


def run_genetic_mutation_control(
    initial_weights: Sequence[float],
    train_fitness: Callable[[tuple[float, ...]], float],
    *,
    config: ESConfig,
) -> dict:
    """Elitist Gaussian genetic-mutation control with exact ES evaluation count.

    Each generation scores 2*pairs+1 offspring: same count as the mirrored
    perturbations plus trial update in ES. Two distinct high-fitness parents may
    carry forward. No crossover/sexual breeding or full Tower retirement logic.
    """
    from agentic_trading.es_research import _validated_config

    starting = tuple(initial_weights)
    _validated_config(config, len(starting))
    if any(not isinstance(v, (int, float)) or isinstance(v, bool)
           or not math.isfinite(v) or abs(v) > config.max_abs_weight for v in starting):
        raise ESResearchError("initial policy weights outside bounded range")
    if not callable(train_fitness):
        raise ESResearchError("training fitness evaluator required")
    rng = random.Random(config.seed)
    start_score = _score(train_fitness, starting)
    elite: list[tuple[float, tuple[float, ...]]] = [(start_score, starting)]
    history: list[dict] = []
    for generation in range(1, config.generations + 1):
        candidates = list(elite)
        parents = tuple(weights for _, weights in elite)
        for _ in range(2 * config.mirrored_pairs + 1):
            parent = parents[rng.randrange(len(parents))]
            weights = tuple(max(-config.max_abs_weight,
                                min(config.max_abs_weight, v + rng.gauss(0, config.sigma)))
                            for v in parent)
            candidates.append((_score(train_fitness, weights), weights))
        candidates.sort(key=lambda pair: -pair[0])
        elite = []
        for candidate in candidates:
            if all(candidate[1] != selected[1] for selected in elite):
                elite.append(candidate)
            if len(elite) == 2:
                break
        history.append({"generation": generation, "best_train_fitness": elite[0][0]})
    return {
        "schema": "atl_ga_mutation_control.v1", "method": "tower_style_mutation_control_not_full_tower",
        "initial_train_fitness": start_score, "final_train_fitness": elite[0][0],
        "final_weights": list(elite[0][1]), "generations": history,
        "fitness_evaluations": 1 + config.generations * (2 * config.mirrored_pairs + 1),
        "research_only": True, "qualified": False, "applied_to_student": False,
        "paper_trading_enabled": False, "live_trading_enabled": False,
    }


def compare_es_and_genetic_mutation(
    initial_weights: Sequence[float],
    train_fitness: Callable[[tuple[float, ...]], float],
    diagnostic_fitness: Callable[[tuple[float, ...]], float],
    *,
    config: ESConfig = ESConfig(),
) -> dict:
    """Compare on identical TRAIN scorer and counts; evaluate diagnostic last.

    Diagnostic calls MUST NOT influence any model selection. The caller is
    responsible for point-in-time and partition checks; callbacks are not a
    sandbox. The diagnostic is illustrative and NEVER a sealed examination.
    """
    if not callable(diagnostic_fitness):
        raise ESResearchError("diagnostic scorer required")
    starting = tuple(initial_weights)
    es = run_es_research(starting, train_fitness, config=config)
    ga = run_genetic_mutation_control(starting, train_fitness, config=config)
    if es["fitness_evaluations"] != ga["fitness_evaluations"]:
        raise ESResearchError("unequal training evaluation budget")
    diagnostic_baseline = _score(diagnostic_fitness, starting)
    es_weights = tuple(es["final_weights"])
    ga_weights = tuple(ga["final_weights"])
    diagnostic_es = _score(diagnostic_fitness, es_weights)
    diagnostic_ga = _score(diagnostic_fitness, ga_weights)
    result = {
        "schema": "atl_es_vs_ga_control.v1",
        "comparison_type": "equal_training_calls_frozen_tape_mutation_control",
        "config": asdict(config),
        "initial_weights_sha256": _hash(starting),
        "train_fitness_evaluations_each": es["fitness_evaluations"],
        "diagnostic_fitness_evaluations_total": 3,
        "training_baseline_fitness": es["initial_train_fitness"],
        "diagnostic_baseline_fitness": diagnostic_baseline,
        "es": {"train_fitness": es["final_train_fitness"],
               "diagnostic_fitness": diagnostic_es, "weights_sha256": _hash(es_weights),
               "history": es["generations"]},
        "genetic_mutation_control": {"train_fitness": ga["final_train_fitness"],
                                    "diagnostic_fitness": diagnostic_ga,
                                    "weights_sha256": _hash(ga_weights),
                                    "history": ga["generations"]},
        "research_only": True, "comparison_is_full_evolution_tower": False,
        "independent_validation": False, "qualified": False,
        "applied_to_student": False, "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }
    result["report_sha256"] = _hash(result)
    return result
