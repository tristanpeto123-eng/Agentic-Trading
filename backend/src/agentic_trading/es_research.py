"""Bounded, pure Evolution Strategies research optimisation.

Uses mirrored Gaussian perturbations with tie-aware centered ranks. This is a
parameter optimiser, NOT a trading engine, model promotion system, or a claim
of trading profitability. The supplied objective must be a frozen, deterministic
training-partition-only evaluation. Out-of-sample evaluation is external.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import random
from typing import Callable, Sequence


class ESResearchError(ValueError):
    """Invalid research settings, non-finite weights or invalid fitness."""


@dataclass(frozen=True)
class ESConfig:
    seed: int = 20261101
    generations: int = 8
    mirrored_pairs: int = 12
    sigma: float = 0.06
    learning_rate: float = 0.03
    max_abs_weight: float = 3.0


def _validated_config(config: ESConfig, dimension: int) -> None:
    if not isinstance(config, ESConfig):
        raise ESResearchError("expected ESConfig")
    if not (1 <= dimension <= 512):
        raise ESResearchError("research policy dimension outside 1..512")
    if (not isinstance(config.seed, int) or isinstance(config.seed, bool)
            or not isinstance(config.generations, int) or isinstance(config.generations, bool)
            or not isinstance(config.mirrored_pairs, int) or isinstance(config.mirrored_pairs, bool)):
        raise ESResearchError("invalid integer ES settings")
    if not (1 <= config.generations <= 30 and 2 <= config.mirrored_pairs <= 64
            and config.generations * config.mirrored_pairs * 2 <= 2048):
        raise ESResearchError("ES evaluation budget exceeded")
    if any(not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x)
           for x in (config.sigma, config.learning_rate, config.max_abs_weight)):
        raise ESResearchError("non-finite ES settings")
    if not (0.0001 <= config.sigma <= 0.5 and 0 < config.learning_rate <= 0.2
            and 0.1 <= config.max_abs_weight <= 6.0):
        raise ESResearchError("ES settings outside bounded research limits")


def _centered_ranks(values: Sequence[float]) -> list[float]:
    """Rank-shape a generation; equal returns get identical, zero-signal ranks."""
    n = len(values)
    if n < 2:
        raise ESResearchError("at least two returns required")
    ranks = [0.0] * n
    order = sorted(range(n), key=lambda i: values[i])
    start = 0
    while start < n:
        end = start + 1
        while end < n and values[order[end]] == values[order[start]]:
            end += 1
        normalized = ((start + end - 1) / 2) / (n - 1) - 0.5
        for k in range(start, end):
            ranks[order[k]] = normalized
        start = end
    return ranks


def run_es_research(
    initial_weights: Sequence[float],
    train_fitness: Callable[[tuple[float, ...]], float],
    *,
    config: ESConfig = ESConfig(),
) -> dict:
    """Run repeatable mirrored ES against a fixed, train-only scalar scorer.

    Candidate updates are accepted only if they strictly improve training
    fitness. This deliberately is *not* validation and grants no permissions.
    Seed reuse only guarantees deterministic output if the scorer is itself
    deterministic on an immutable, correctly partitioned training snapshot.
    """
    original = tuple(initial_weights)
    _validated_config(config, len(original))
    if any(not isinstance(x, (float, int)) or isinstance(x, bool)
           or not math.isfinite(x) or abs(x) > config.max_abs_weight for x in original):
        raise ESResearchError("initial policy weights outside bounded range")
    if not callable(train_fitness):
        raise ESResearchError("training fitness evaluator required")

    def score(weights: tuple[float, ...]) -> float:
        result = train_fitness(weights)
        if not isinstance(result, (int, float)) or isinstance(result, bool) or not math.isfinite(result):
            raise ESResearchError("fitness must be a finite numeric scalar")
        return float(result)

    rng = random.Random(config.seed)
    current = original
    incumbent_score = score(current)
    baseline_score = incumbent_score
    history = []
    for generation in range(1, config.generations + 1):
        noise_vectors = []
        scores = []
        for _ in range(config.mirrored_pairs):
            noise = tuple(rng.gauss(0.0, 1.0) for _ in current)
            noise_vectors.append(noise)
            plus = tuple(max(-config.max_abs_weight, min(config.max_abs_weight, weight + config.sigma * delta))
                         for weight, delta in zip(current, noise))
            minus = tuple(max(-config.max_abs_weight, min(config.max_abs_weight, weight - config.sigma * delta))
                          for weight, delta in zip(current, noise))
            scores.extend((score(plus), score(minus)))
        ranks = _centered_ranks(scores)
        # ES directional estimate using rank shaping and antithetic pairs.
        # Noise magnitude and step sizes are bounded; no gradient backprop.
        updated = []
        for coordinate, weight in enumerate(current):
            estimate = sum((ranks[2 * i] - ranks[2 * i + 1]) * noise_vectors[i][coordinate]
                           for i in range(config.mirrored_pairs)) / (config.mirrored_pairs * config.sigma)
            updated.append(max(-config.max_abs_weight, min(config.max_abs_weight,
                                                           weight + config.learning_rate * estimate)))
        trial = tuple(updated)
        trial_score = score(trial)
        accepted = trial_score > incumbent_score
        if accepted:
            current, incumbent_score = trial, trial_score
        history.append({"generation": generation, "accepted": accepted,
                        "train_fitness": incumbent_score, "trial_train_fitness": trial_score,
                        "candidate_fitness_min": min(scores), "candidate_fitness_max": max(scores)})

    payload = {
        "schema": "atl_es_research.v1", "optimizer": "mirrored_centered_rank_ES",
        "config": asdict(config),
        "initial_weights_sha256": sha256(json.dumps(original, separators=(",", ":")).encode()).hexdigest(),
        "initial_train_fitness": baseline_score,
        "final_train_fitness": incumbent_score,
        "final_weights": list(current), "generations": history,
        "fitness_evaluations": 1 + config.generations * (2 * config.mirrored_pairs + 1),
        "research_only": True, "independent_validation": False,
        "qualified": False, "paper_trading_enabled": False, "live_trading_enabled": False,
        "applied_to_student": False,
    }
    payload["report_sha256"] = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                                 allow_nan=False).encode()).hexdigest()
    return payload
