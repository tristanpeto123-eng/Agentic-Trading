"""Read-only Academy candle study over an integrity-checked XAUUSD M15 dataset.

An online, chronological *directional observation* lab: fixed elementary signal
rules are not trained, and the market-specific selector is revised only after
each five completed training batches. No order fills, trade episodes, financial
P&L, neural checkpoints, broker connectivity, promotion, or holdout inspection.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Sequence

from agentic_trading.chronological_holdout import split_chronological
from agentic_trading.data_engine import Candle, STEP

TACTICS = ("trend", "range", "breakout")
LOOKBACK = 4
BATCH_SIZE = 96
UPDATE_EVERY = 5


class CandleStudyError(ValueError):
    """Historical study cannot be completed safely with the supplied candles."""


def _direction(value: Decimal) -> int:
    return (value > 0) - (value < 0)


def _forecast(bars: Sequence[Candle], i: int, tactic: str) -> int:
    """Signal at the close of bar i, using no later data or trade outcomes."""
    last = Decimal(bars[i].close)
    previous = Decimal(bars[i - 1].close)
    if tactic == "trend":
        return _direction(last - previous)
    if tactic == "range":
        return -_direction(last - previous)
    if tactic == "breakout":
        ceiling = max(Decimal(bar.high) for bar in bars[i-LOOKBACK:i])
        floor = min(Decimal(bar.low) for bar in bars[i-LOOKBACK:i])
        return int(last > ceiling) - int(last < floor)
    raise CandleStudyError("Unsupported fixed observation tactic")


def _empty() -> dict[str, int]:
    return {"observations": 0, "correct": 0}


def _accuracy(entry: dict[str, int]) -> float | None:
    n = entry["observations"]
    return round(100 * entry["correct"] / n, 2) if n else None


def _evaluate(
    bars: Sequence[Candle], start: int, end: int, tactics: tuple[str, ...]
) -> tuple[dict[str, dict[str, int]], int]:
    counts = {key: _empty() for key in tactics}
    skipped = 0
    # i + 1 is the labelled, subsequently completed candle. Never use that
    # candle's prices as a feature at decision time i.
    for i in range(max(LOOKBACK, start), end - 1):
        # Any absent M15 bar inside the lookback/label span invalidates the
        # observation. We do not fill weekends or sessions synthetically.
        if any(bars[j].open_time - bars[j - 1].open_time != STEP
               for j in range(i - LOOKBACK + 1, i + 2)):
            skipped += 1
            continue
        actual = _direction(Decimal(bars[i + 1].close) - Decimal(bars[i].close))
        if not actual:
            skipped += 1
            continue
        for key in tactics:
            forecast = _forecast(bars, i, key)
            if not forecast:
                continue
            counts[key]["observations"] += 1
            counts[key]["correct"] += int(forecast == actual)
    return counts, skipped


def _combine(samples: Sequence[dict[str, dict[str, int]]], key: str) -> dict[str, int]:
    return {
        "observations": sum(x[key]["observations"] for x in samples),
        "correct": sum(x[key]["correct"] for x in samples),
    }


def study_candles(
    candles: Sequence[Candle],
    *,
    dataset_id: str,
    source_sha256: str,
    allowed_tactics: tuple[str, ...] = TACTICS,
    batch_size: int = BATCH_SIZE,
    embargo_bars: int = 96,
) -> dict:
    if not dataset_id or len(source_sha256) != 64:
        raise CandleStudyError("Frozen source metadata missing")
    tactics = tuple(key for key in TACTICS if key in allowed_tactics)
    if not tactics:
        raise CandleStudyError("Student has no supported study tactics (trend/range/breakout)")
    if not 24 <= batch_size <= 512:
        raise CandleStudyError("Study batch size must be 24..512")
    if embargo_bars < LOOKBACK + 1:
        raise CandleStudyError("Embargo too short for study's lookback/label horizon")
    try:
        split = split_chronological(candles, embargo_bars=embargo_bars, minimum_per_fold=100)
    except (AttributeError, TypeError, ValueError) as exc:
        raise CandleStudyError(f"Chronological partition refused: {exc}") from exc

    # Keep holdout physically untouched. The final 20% is sealed; even
    # summary P&L/accuracy must not be computed or returned from it.
    training = split.train
    validation = split.validation
    current = tactics[0]
    version = 1
    history: list[dict] = []
    candidate_batches: list[dict[str, dict[str, int]]] = []
    cumulative = _empty()
    for start in range(0, len(training), batch_size):
        end = min(start + batch_size, len(training))
        candidate, skipped = _evaluate(training, start, end, tactics)
        chosen = candidate[current]
        cumulative["correct"] += chosen["correct"]
        cumulative["observations"] += chosen["observations"]
        candidate_batches.append(candidate)
        number = len(history) + 1
        point = {
            "batch": number,
            "start_at": training[start].open_time.isoformat(),
            "end_at": training[end - 1].available_at.isoformat(),
            "close": training[end - 1].close,
            "bars": end - start,
            "selected_rule": current,
            "selector_version": version,
            "observations": chosen["observations"],
            "correct": chosen["correct"],
            "accuracy_pct": _accuracy(chosen),
            "cumulative_accuracy_pct": _accuracy(cumulative),
            "skipped": skipped,
            "updated_after": False,
        }
        if number % UPDATE_EVERY == 0:
            recent = candidate_batches[-UPDATE_EVERY:]
            scores = {key: _combine(recent, key) for key in tactics}
            eligible = [key for key in tactics if scores[key]["observations"] >= 20]
            if eligible:
                current = max(eligible, key=lambda key: (
                    scores[key]["correct"] / scores[key]["observations"],
                    scores[key]["observations"], -tactics.index(key),
                ))
            # Only the student's fixed-rule selector is versioned. Shared
            # tactics themselves and any neural model weights remain frozen.
            version += 1
            point["updated_after"] = True
            point["next_selected_rule"] = current
            point["next_selector_version"] = version
        history.append(point)

    val_samples = []
    validation_skipped = 0
    for start in range(0, len(validation), batch_size):
        end = min(start + batch_size, len(validation))
        scored, skipped = _evaluate(validation, start, end, (current,))
        val_samples.append(scored)
        validation_skipped += skipped
    score = _combine(val_samples, current) if val_samples else _empty()
    return {
        "schema_version": "academy_candle_study.v1",
        "dataset_id": dataset_id,
        "source_sha256": source_sha256,
        "split_manifest_sha256": split.manifest_sha256,
        "market": "XAUUSD",
        "timeframe": "M15",
        "mode": "historical_directional_observation_only",
        "source_verified": False,
        "research_eligible": False,
        "trade_execution_performed": False,
        "net_pnl_usd": None,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "neural_training_performed": False,
        "fixed_rules": list(tactics),
        "batch_size": batch_size,
        "update_every_batches": UPDATE_EVERY,
        "training_bars": len(training),
        "validation_bars": len(validation),
        "sealed_holdout_bars": len(split.test),
        "holdout_evaluated": False,
        "selector_version": version,
        "selected_rule": current,
        "training": {
            **cumulative, "accuracy_pct": _accuracy(cumulative),
        },
        "development_validation": {
            **score, "accuracy_pct": _accuracy(score),
            "skipped": validation_skipped,
            "selector_frozen": True,
        },
        "batches": history,
        "warnings": [
            "Owner-supplied M15 candles remain source- and rights-unverified.",
            "Directional classification is NOT costed trade performance, win rate, P&L or model mastery.",
            "Tactics are fixed heuristics; only an exploratory selector changes every five training batches.",
            "Development validation does not qualify an agent. The final holdout is sealed.",
        ],
    }
