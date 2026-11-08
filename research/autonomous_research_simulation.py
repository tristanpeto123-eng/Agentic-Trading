"""Bounded, research-only autonomous BID/ASK replay and five-batch selection.

Fixed signal skills; no broker, online training, or evaluation-driven retraining.
The final sealed test is opened exactly once after training stops.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from research.costed_bid_ask_replay import replay_signals
from research.pair_qualification import _rows
from research.dataset_evidence import dataset_manifest
from research.five_batch_policy_trainer import FiveBatchPolicyTrainer

SKILLS = ("momentum", "reversion", "flat")


def _signals(closes, skill, start, end):
    signals = [0] * len(closes)
    for i in range(max(1, start), min(end - 2, len(closes) - 2)):
        delta = closes[i] - closes[i - 1]
        direction = (delta > 0) - (delta < 0)
        signals[i] = direction if skill == "momentum" else -direction if skill == "reversion" else 0
    return signals


def _score(records, capital, max_drawdown_pct):
    """Score only through the first risk breach; replay itself is not a kill switch.

    The pure offline replay may already have produced later trades. Disclose
    their count separately instead of counting them toward the risk-stopped
    evaluation or implying that real-world execution was halted.
    """
    equity = capital
    peak = capital
    max_dd = 0.0
    gains = losses = 0.0
    evaluated = 0
    for evaluated, trade in enumerate(records, start=1):
        pnl = trade["net"]  # one unit, unleveraged, costs already deducted
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100)
        gains += max(0.0, pnl)
        losses += max(0.0, -pnl)
        if equity <= 0 or max_dd > max_drawdown_pct:
            return {"trades": evaluated, "replayed_trades": len(records),
                    "net": equity - capital,
                    "profit_factor": gains / losses if losses else (None if not gains else 1e12),
                    "drawdown_pct": max_dd, "risk_stopped": True,
                    "risk_stop_scoring_only": True}
    return {"trades": evaluated, "replayed_trades": len(records),
            "net": equity - capital,
            "profit_factor": gains / losses if losses else (None if not gains else 1e12),
            "drawdown_pct": max_dd, "risk_stopped": False,
            "risk_stop_scoring_only": True}


def _pass(metrics, min_trades, min_pf, max_dd):
    pf = metrics["profit_factor"]
    return (not metrics["risk_stopped"] and metrics["trades"] >= min_trades
            and pf is not None and pf >= min_pf and metrics["net"] > 0
            and metrics["drawdown_pct"] <= max_dd)


def run(bid, ask, provenance, *, output, fee, slippage, capital=10000.0,
        max_generations=20, patience=4, min_trades=100,
        min_profit_factor=1.30, max_drawdown_pct=10.0, evaluation_windows=3):
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")
    if any(not math.isfinite(v) or v < 0 for v in (fee, slippage, max_drawdown_pct)):
        raise ValueError("invalid costs or drawdown")
    if not math.isfinite(capital) or capital <= 0 or max_drawdown_pct <= 0:
        raise ValueError("invalid capital or risk cap")
    if not math.isfinite(min_profit_factor) or min_profit_factor < 1:
        raise ValueError("invalid profit factor")
    if any(type(v) is not int or v < 1 for v in
           (max_generations, patience, min_trades, evaluation_windows)):
        raise ValueError("invalid integer parameter")
    manifest = dataset_manifest(bid, ask, provenance=provenance)
    closes = [row[4] for row in _rows(bid)]
    n = len(closes)
    # Disjoint 60% train / 15% development validation / 25% sealed test.
    train_end, validation_end = int(n * .60), int(n * .75)
    test_size = (n - validation_end) // evaluation_windows
    if train_end < 30 or validation_end - train_end < 5 or test_size < 5:
        raise ValueError("insufficient chronological data")
    if test_size - 2 < min_trades:
        raise ValueError("insufficient independent test candles for minimum trade count")
    if Path(output).resolve() in (Path(bid).resolve(), Path(ask).resolve()):
        raise ValueError("output must not overwrite market data")
    # Precompute train-only scores; no validation or test result enters trainer.
    def replay(skill, start, end):
        result = replay_signals(bid, ask, _signals(closes, skill, start, end),
                                provenance=provenance, fee_per_round_trip=fee,
                                slippage_per_side=slippage)
        return result["trade_records"]
    trainer = FiveBatchPolicyTrainer(SKILLS)
    batch_size = train_end // (max_generations * 5)
    if batch_size < 3:
        raise ValueError("insufficient training candles for requested generations")
    history = []
    best_skill = None
    best_validation = float("-inf")
    stale = 0
    for generation in range(max_generations):
        snapshot = None
        for b in range(5):
            index = generation * 5 + b
            start, end = index * batch_size, (index + 1) * batch_size
            rewards = {s: sum(t["net"] for t in replay(s, start, end)) for s in SKILLS}
            # Existing trainer requires development validation at five-batch boundaries.
            validation = ({s: sum(t["net"] for t in replay(s, train_end, validation_end))
                           for s in SKILLS} if b == 4 else None)
            snapshot = trainer.ingest_batch(rewards, validation_rewards=validation)
        selected = snapshot.preferred_skill
        validation_net = snapshot.validation_net
        # Validation is used only for checkpoint/early-stop, never to rank skills.
        improved = validation_net > best_validation
        if improved:
            best_skill, best_validation, stale = selected, validation_net, 0
        else:
            stale += 1
        history.append({"generation": generation + 1, "batches": snapshot.batches_seen,
                        "training_selected_skill": selected,
                        "development_validation_net": validation_net,
                        "best_updated": improved})
        if stale >= patience:
            break
    # Seal: training loop is over. Evaluate the frozen candidate exactly once.
    windows = []
    for w in range(evaluation_windows):
        start = validation_end + w * test_size
        end = (validation_end + (w + 1) * test_size
               if w < evaluation_windows - 1 else n)
        metrics = _score(replay(best_skill, start, end), capital, max_drawdown_pct)
        metrics["window"] = w + 1
        metrics["passed"] = _pass(metrics, min_trades, min_profit_factor, max_drawdown_pct)
        windows.append(metrics)
    result = {
        "status": "ceo_review_required" if all(w["passed"] for w in windows) else "research_failed",
        "dataset_manifest": manifest,
        "policy": {"skill": best_skill, "frozen_fingerprint": trainer.fingerprint,
                   "batches_seen": len(trainer.batches), "generations": len(history)},
        "development_history": history, "sealed_evaluation": windows,
        "criteria": {"min_trades_per_window": min_trades,
                     "min_profit_factor": min_profit_factor,
                     "max_drawdown_pct": max_drawdown_pct,
                     "profitable_independent_windows": evaluation_windows},
        "checkpoint": {"kind": "fixed_skill_selector", "ceo_approved": False,
                       "promoted": False, "execution_authorized": False,
                       "live_authorized": False},
        "holdout_used_for_training": False, "license_verified": False,
        "warning": "Research-only fixed-skill selection; no trained neural model or demonstrated future profitability."
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".research-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("bid", "ask", "provenance", "output"):
        p.add_argument("--" + flag, required=True)
    p.add_argument("--fee", type=float, default=0.0)
    p.add_argument("--slippage", type=float, default=0.0)
    p.add_argument("--max-generations", type=int, default=20)
    args = p.parse_args()
    run(args.bid, args.ask, json.loads(Path(args.provenance).read_text()),
        output=args.output, fee=args.fee, slippage=args.slippage,
        max_generations=args.max_generations)


if __name__ == "__main__":
    main()
