"""Persistent CPU-only M15 research learner, separate from S6 episodic trainer.

This is ACTUAL NumPy neural gradient training. It does not turn simulated next-bar
outcomes into independently verified profitability, trading, or a Scout B score.
No broker imports, trained-policy activation, or sealed holdout access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from zipfile import BadZipFile
import json
import math
from uuid import uuid4

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentic_trading.data_engine import parse_iso_utc
from agentic_trading.storage import ResearchNeuralRun, ResearchNeuralEpoch

FEATURE_COUNT = 8
HIDDEN = 16
EPOCH_LIMIT = 80
BAR_STEP = timedelta(minutes=15)
RULES = ("trend", "range", "breakout")
MODEL_SCHEMA = "research_m15_outcome_mlp8x16x2.v2"


class ResearchNeuralError(ValueError):
    pass


def _sha(obj: object) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def build_training_snapshot(bars: list[dict], *, market: str, tactic: str,
                            source_sha256: str, plan_version: int) -> dict:
    """Train/development only. NEVER materialise labels in the final 20% holdout."""
    if market not in ("XAUUSD", "BTCUSD") or tactic not in RULES:
        raise ResearchNeuralError("Unsupported historical research market or tactic")
    if len(bars) < 650 or len(bars) > 2300:
        raise ResearchNeuralError("Need 650–2300 completed M15 bars for embargoed neural training")
    if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ResearchNeuralError("Missing hashed historical source provenance")
    times, prices = [], []
    now = datetime.now(timezone.utc)
    for candle in bars:
        try:
            stamp = parse_iso_utc(candle["open_time"])
            values = np.array([float(candle[k]) for k in ("open", "high", "low", "close")], dtype=np.float64)
            if not np.isfinite(values).all() or np.min(values) <= 0:
                raise ValueError("nonfinite or negative prices")
            o, h, l, c = values
            if h < max(o, l, c) or l > min(o, h, c):
                raise ValueError("OHLC bounds invalid")
        except (TypeError, ValueError, KeyError) as exc:
            raise ResearchNeuralError("Historical candle invalid") from exc
        if times and stamp <= times[-1]:
            raise ResearchNeuralError("Historical candles must be strictly chronological")
        if stamp + BAR_STEP > now:
            raise ResearchNeuralError("Future or uncompleted historical candle")
        times.append(stamp)
        prices.append(values)
    arr = np.stack(prices)
    split_train = int(len(bars) * 0.6)
    split_holdout = int(len(bars) * 0.8)
    # Both sides of development get a 96-bar embargo; holdout is never inspected.
    train_end = split_train - 96
    dev_begin = split_train + 96
    dev_end = split_holdout - 96
    if dev_end - dev_begin < 30:
        raise ResearchNeuralError("Not enough isolated development labels after embargo")
    def sample(i: int) -> dict | None:
        if i < 5 or i + 1 >= len(bars):
            return None
        if any(times[k] - times[k-1] != BAR_STEP for k in range(i-4, i+2)):
            return None
        o, h, l, close = arr[i]
        prev_close = arr[i-1,3]
        older_close = arr[i-4,3]
        if abs(close/prev_close - 1) > .04:
            return None
        if tactic == "trend":
            side = np.sign(close-prev_close)
        elif tactic == "range":
            side = -np.sign(close-prev_close)
        else:
            high = float(np.max(arr[i-4:i,1]))
            low = float(np.min(arr[i-4:i,2]))
            side = int(close > high) - int(close < low)
        if side == 0:
            return None
        last = arr[i-4:i+1]
        high_window, low_window = float(np.max(last[:,1])), float(np.min(last[:,2]))
        span = max(high_window - low_window, 1e-8)
        features = [
            100 * (close / prev_close - 1),
            100 * (close / older_close - 1),
            100 * (close / o - 1),
            100 * (h - l) / close,
            (close - low_window) / span - 0.5,
            float(side),
            1.0 if market == "BTCUSD" else 0.0,
            (float((times[i].hour * 60 + times[i].minute) // 15) / 96) - 0.5,
        ]
        features = [float(np.clip(v, -5., 5.)) for v in features]
        entry, exit_price = float(arr[i+1, 0]), float(arr[i+1, 3])
        # Indicative, fixed friction: BTC 0.2% notional or XAU $1/oz RT.
        cost_per_unit = entry * .002 if market == "BTCUSD" else 1.
        net_pct = float(np.clip(100 * (side * (exit_price - entry) - cost_per_unit) / entry, -5., 5.))
        return {"at": times[i].isoformat(), "available": (times[i+1]+BAR_STEP).isoformat(),
                "f": features, "net": net_pct, "win": int(net_pct > 0)}
    train = [v for i in range(5, train_end) if (v := sample(i)) is not None]
    develop = [v for i in range(dev_begin, dev_end) if (v := sample(i)) is not None]
    if len(train) < 80 or len(develop) < 20:
        raise ResearchNeuralError("Insufficient actual closed training examples or development examples")
    # UTC phase is invariant to weekend closures or missing earlier candles.
    # Any local non-contiguous signal window is still skipped in sample().
    # No holdout feature, label, outcome or trade is generated, read or persisted.
    frozen = {
        "schema": MODEL_SCHEMA, "source_sha256": source_sha256,
        "market": market, "tactic": tactic, "plan_version": plan_version,
        "bar_count": len(bars),
        "source_has_m15_gaps": any(b - a != BAR_STEP for a,b in zip(times, times[1:])),
        "source_start_utc": times[0].isoformat(),
        "input_ohlc_schema": "completed_m15_ohlc.v1",
        "training_last_utc": train[-1]["available"],
        "development_last_utc": develop[-1]["available"],
        "embargo_bars": 96, "holdout_fraction_unread": 0.2,
        "source_verified": False, "execution_cost_verified": False,
        "train": train, "development": develop,
    }
    return frozen


def _initial_weights(run_id: str) -> dict[str, np.ndarray]:
    seed = int(sha256(run_id.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    return {
        "w1": rng.normal(0, .15, (FEATURE_COUNT, HIDDEN)).astype(np.float64),
        "b1": np.zeros(HIDDEN, dtype=np.float64),
        "w2": rng.normal(0, .15, (HIDDEN, 2)).astype(np.float64),
        "b2": np.zeros(2, dtype=np.float64),
    }


def _save_weights(weights: dict[str, np.ndarray]) -> bytes:
    stream = BytesIO()
    np.savez_compressed(stream, **weights)
    return stream.getvalue()


def _restore_weights(blob: bytes, digest: str) -> dict[str, np.ndarray]:
    if len(blob) > 50000 or sha256(blob).hexdigest() != digest:
        raise ResearchNeuralError("Persisted neural weights checksum invalid")
    try:
        with np.load(BytesIO(blob), allow_pickle=False) as data:
            if set(data.files) != {"w1", "b1", "w2", "b2"}:
                raise ResearchNeuralError("Persisted neural model keys invalid")
            result = {k: data[k].copy() for k in data.files}
    except (ValueError, KeyError, OSError, BadZipFile) as exc:
        raise ResearchNeuralError("Persisted neural checkpoint cannot be read") from exc
    expected = {"w1": (FEATURE_COUNT, HIDDEN), "b1": (HIDDEN,),
                "w2": (HIDDEN, 2), "b2": (2,)}
    if any(v.shape != expected[k] or v.dtype != np.float64 or not np.isfinite(v).all()
           for k,v in result.items()):
        raise ResearchNeuralError("Persisted neural weights shape/value invalid")
    return result


def _arrays(rows: list[dict]):
    x = np.asarray([r["f"] for r in rows], dtype=np.float64)
    y = np.asarray([[r["win"], r["net"]] for r in rows], dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != FEATURE_COUNT or y.shape != (len(rows), 2):
        raise ResearchNeuralError("Frozen examples have invalid shape")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ResearchNeuralError("Frozen examples contain nonfinite values")
    return x, y


def _forward(w: dict, x: np.ndarray):
    pre = x @ w["w1"] + w["b1"]
    hidden = np.maximum(pre, 0.)
    logits = hidden @ w["w2"] + w["b2"]
    return pre, hidden, logits


def _objective(pred: np.ndarray, y: np.ndarray) -> float:
    binary = np.logaddexp(0, pred[:,0]) - y[:,0] * pred[:,0]
    delta = pred[:,1] - y[:,1]
    huber = np.where(abs(delta) < 1, .5*delta*delta, abs(delta)-.5)
    result = float(np.mean(binary + .2*huber))
    if not math.isfinite(result):
        raise ResearchNeuralError("Nonfinite objective")
    return result


def _gradient_step(weights: dict, x: np.ndarray, y: np.ndarray, lr: float = .035):
    pre, hidden, pred = _forward(weights, x)
    z = np.clip(pred[:,0], -50, 50)
    sigmoid = 1 / (1 + np.exp(-z))
    delta = (pred[:,1] - y[:,1])
    d = np.stack([(sigmoid-y[:,0])/len(x), .2*np.clip(delta, -1, 1)/len(x)], axis=1)
    d_w2 = hidden.T @ d
    d_b2 = d.sum(axis=0)
    dh = d @ weights["w2"].T
    dh[pre <= 0] = 0
    d_w1 = x.T @ dh
    d_b1 = dh.sum(axis=0)
    grads = {"w1": d_w1, "b1": d_b1, "w2": d_w2, "b2": d_b2}
    if any(not np.isfinite(v).all() for v in grads.values()):
        raise ResearchNeuralError("Invalid neural gradient")
    return {k: weights[k] - lr * grads[k] for k in weights}


def _checkpoint(session: Session, run_id: str):
    return session.scalar(select(ResearchNeuralEpoch)
        .where(ResearchNeuralEpoch.run_id == run_id)
        .order_by(ResearchNeuralEpoch.epoch.desc()).limit(1))


def get_run_report(session: Session, student_id: str, run_id: str | None = None) -> dict | None:
    query = select(ResearchNeuralRun).where(ResearchNeuralRun.student_id == student_id)
    if run_id:
        query = query.where(ResearchNeuralRun.id == run_id)
    else:
        query = query.order_by(ResearchNeuralRun.created_at.desc(),
                               ResearchNeuralRun.id.desc()).limit(1)
    run = session.scalar(query)
    if run is None:
        return None
    if _sha(run.frozen_examples) != run.snapshot_sha256:
        raise ResearchNeuralError("Frozen training snapshot failed integrity verification")
    checkpoints = session.scalars(select(ResearchNeuralEpoch)
        .where(ResearchNeuralEpoch.run_id == run.id)
        .order_by(ResearchNeuralEpoch.epoch.asc())).all()
    # Verify every immutable checkpoint on status retrieval, including after web restarts.
    for index, cp in enumerate(checkpoints, 1):
        if cp.epoch != index:
            raise ResearchNeuralError("Training checkpoint sequence is incomplete")
        _restore_weights(cp.weights_npz, cp.weights_sha256)
    last = checkpoints[-1] if checkpoints else None
    return {
        "run_id": run.id, "student_id": student_id, "market": run.market,
        "tactic": run.tactic, "model_schema": run.frozen_examples.get("schema", "legacy"),
        "epochs_planned": run.epochs_planned, "epoch": last.epoch if last else 0,
        "state": "complete" if last and last.epoch >= run.epochs_planned else "research_training",
        "train_examples": len(run.frozen_examples["train"]),
        "development_examples": len(run.frozen_examples["development"]),
        "snapshot_sha256": run.snapshot_sha256,
        "source_sha256": run.source_sha256,
        "latest_weights_sha256": last.weights_sha256 if last else None,
        "metrics": [{"epoch": cp.epoch, "train_loss": cp.train_loss,
                     "development_loss": cp.development_loss} for cp in checkpoints],
        "weights_persisted": bool(last), "can_resume": bool(last) and last.epoch < run.epochs_planned,
        "qualification": "unqualified", "independent_holdout_evaluated": False,
        "trained_neural_model": bool(last), "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "note": "Genuine CPU neural gradient training, immutable database checkpoints. Only TRAIN/development historical labels; no untouched final holdout or broker fills evaluated. Model is unqualified: research-only diagnostic inference is available, but no Guardian authorization or broker route is connected.",
    }


def create_run(session: Session, student_id: str, *, market: str,
               tactic: str, plan_version: int, bars: list[dict],
               source_sha256: str) -> dict:
    # An unfinished saved run can resume from its original frozen snapshot
    # even if a newer public feed later has different candles.
    existing = get_run_report(session, student_id)
    if (existing is not None and existing["state"] != "complete"
            and existing["model_schema"] == MODEL_SCHEMA):
        return existing
    frozen = build_training_snapshot(bars, market=market, tactic=tactic,
                                     source_sha256=source_sha256,
                                     plan_version=plan_version)
    run = ResearchNeuralRun(
        id=str(uuid4()), student_id=student_id, market=market,
        tactic=tactic, plan_version=plan_version,
        source_sha256=source_sha256,
        snapshot_sha256=_sha(frozen), frozen_examples=frozen,
        epochs_planned=EPOCH_LIMIT, state="research_only",
        qualification="unqualified",
    )
    session.add(run)
    session.commit()
    return get_run_report(session, student_id, run.id)


def train_one_epoch(session: Session, student_id: str, run_id: str,
                    expected_epoch: int) -> dict:
    # Database row lock serializes progress in PostgreSQL; epoch compare
    # prevents duplicate/reordered browser requests from advancing the run.
    run = session.scalar(select(ResearchNeuralRun).where(
        ResearchNeuralRun.id == run_id, ResearchNeuralRun.student_id == student_id
    ).with_for_update())
    if run is None:
        raise ResearchNeuralError("Training run not found for student")
    if _sha(run.frozen_examples) != run.snapshot_sha256:
        raise ResearchNeuralError("Frozen training data modified")
    last = _checkpoint(session, run.id)
    current = last.epoch if last else 0
    if current != expected_epoch:
        raise ResearchNeuralError("Epoch already advanced; refresh saved training state")
    if current >= run.epochs_planned:
        return get_run_report(session, student_id, run_id)
    weights = _restore_weights(last.weights_npz, last.weights_sha256) if last else _initial_weights(run.id)
    train_x, train_y = _arrays(run.frozen_examples["train"])
    dev_x, dev_y = _arrays(run.frozen_examples["development"])
    next_weights = _gradient_step(weights, train_x, train_y)
    _, _, t = _forward(next_weights, train_x)
    _, _, v = _forward(next_weights, dev_x)
    blob = _save_weights(next_weights)
    session.add(ResearchNeuralEpoch(
        run_id=run.id, epoch=current+1, weights_npz=blob,
        weights_sha256=sha256(blob).hexdigest(),
        train_loss=_objective(t, train_y),
        development_loss=_objective(v, dev_y),
    ))
    session.commit()
    return get_run_report(session, student_id, run_id)



def load_neural_inference(session: Session, student_id: str,
                          *, plan_version: int) -> dict | None:
    """Load the student-owned, hash-verified saved neural checkpoint (no writes).

    Old snapshots lacking a source time origin are rejected, not guessed: the
    model's phase feature is indexed relative to the original dataset start.
    """
    report = get_run_report(session, student_id)
    if not report or report["epoch"] == 0:
        return None
    run = session.get(ResearchNeuralRun, report["run_id"])
    if not run or run.plan_version != plan_version:
        raise ResearchNeuralError("Saved neural model belongs to an older learning plan")
    frozen = run.frozen_examples
    if frozen.get("schema") != MODEL_SCHEMA or frozen.get("input_ohlc_schema") != "completed_m15_ohlc.v1":
        raise ResearchNeuralError("Legacy checkpoint has an incompatible input feature schema; retrain required")
    try:
        origin = parse_iso_utc(frozen["source_start_utc"])
        training_end = parse_iso_utc(frozen["training_last_utc"])
        development_end = parse_iso_utc(frozen["development_last_utc"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ResearchNeuralError("Neural model time provenance incomplete") from exc
    if not origin < training_end < development_end:
        raise ResearchNeuralError("Neural model snapshot time order invalid")
    cp = _checkpoint(session, run.id)
    if not cp or cp.epoch != report["epoch"] or cp.weights_sha256 != report["latest_weights_sha256"]:
        raise ResearchNeuralError("Neural checkpoint version or hash inconsistent")
    weights = _restore_weights(cp.weights_npz, cp.weights_sha256)
    return {
        "market": run.market, "tactic": run.tactic, "run_id": run.id,
        "epoch": cp.epoch, "weights_sha256": cp.weights_sha256,
        "origin": origin, "training_end": training_end,
        "development_end": development_end,
        "snapshot_sha256": run.snapshot_sha256, "weights": weights,
        "model_schema": MODEL_SCHEMA,
    }


def _closed_signal_features(bars: list, market: str, tactic: str,
                            origin: datetime) -> tuple[np.ndarray, datetime]:
    """Exactly the eight training-time features; the next candle is never read."""
    if len(bars) < 5 or market not in ("XAUUSD", "BTCUSD") or tactic not in RULES:
        raise ResearchNeuralError("No suitable closed M15 context for neural inference")
    stamps = []
    prices = []
    for bar in bars[-5:]:
        def attr(key):
            return bar[key] if isinstance(bar, dict) else getattr(bar, key)
        stamp = parse_iso_utc(attr("open_time")) if isinstance(attr("open_time"), str) else attr("open_time")
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
            raise ResearchNeuralError("Neural candle time must be UTC")
        row = np.asarray([float(attr(k)) for k in ("open", "high", "low", "close")], dtype=np.float64)
        if not np.isfinite(row).all() or row.min() <= 0 or row[1] < max(row[0], row[2], row[3]) or row[2] > min(row[0], row[1], row[3]):
            raise ResearchNeuralError("Neural candle values invalid")
        stamps.append(stamp)
        prices.append(row)
    if any(y - x != BAR_STEP for x,y in zip(stamps, stamps[1:])):
        raise ResearchNeuralError("M15 gaps prevent neural inference")
    last = stamps[-1]
    index_offset = (last - origin).total_seconds() / 900
    if index_offset < 5 or not index_offset.is_integer():
        raise ResearchNeuralError("Model input outside frozen dataset alignment")
    a = np.stack(prices)
    o, h, l, close = a[-1]
    prev_close, older_close = a[-2,3], a[-5,3]
    if abs(close/prev_close - 1) > .04:
        raise ResearchNeuralError("Abrupt-price guard blocks neural inference")
    if tactic == "trend":
        side = np.sign(close-prev_close)
    elif tactic == "range":
        side = -np.sign(close-prev_close)
    else:
        side = int(close > np.max(a[:-1,1])) - int(close < np.min(a[:-1,2]))
    if side == 0:
        raise ResearchNeuralError("No strategy signal for neural inference")
    low_window, high_window = float(np.min(a[:,2])), float(np.max(a[:,1]))
    span = max(high_window-low_window, 1e-8)
    vector = [
        100 * (close/prev_close - 1),
        100 * (close/older_close - 1),
        100 * (close/o - 1),
        100 * (h-l)/close,
        (close-low_window)/span-.5,
        float(side),
        1.0 if market == "BTCUSD" else 0.0,
        (float((last.hour * 60 + last.minute) // 15) / 96)-.5,
    ]
    return np.asarray([float(np.clip(v, -5, 5)) for v in vector], dtype=np.float64), last+BAR_STEP


def score_neural_candidate(context: dict, candles: list, *,
                           market: str, tactic: str) -> dict:
    """Model-generated but uncalibrated candidate diagnostics, never order approval."""
    if context["market"] != market or context["tactic"] != tactic:
        return {"status": "MODEL_SCOPE_MISMATCH", "recommendation": "ABSTAIN"}
    try:
        vector, available_at = _closed_signal_features(candles, market, tactic, context["origin"])
    except ResearchNeuralError as exc:
        # Normal "no strategy signal" / closed-market gaps are abstentions,
        # not infrastructure failures. Never fabricate a neural prediction.
        normal = {
            "No strategy signal for neural inference": "NO_STRATEGY_SIGNAL",
            "M15 gaps prevent neural inference": "GAPPED_SIGNAL_WINDOW",
        }
        status = normal.get(str(exc))
        if status is None:
            raise
        return {
            "status": status, "recommendation": "ABSTAIN",
            "reason": str(exc), "checkpoint_sha256": context["weights_sha256"],
            "epoch": context["epoch"], "prediction_uncalibrated": True,
            "guardian_authorised": False,
        }
    _, _, prediction = _forward(context["weights"], vector.reshape((1, FEATURE_COUNT)))
    raw = prediction[0]
    if not np.isfinite(raw).all():
        raise ResearchNeuralError("Neural prediction nonfinite")
    probability = float(1 / (1 + np.exp(-np.clip(raw[0], -50, 50))))
    net_pct = float(raw[1])
    stage = ("TRAINING_PERIOD_DIAGNOSTIC" if available_at <= context["training_end"] else
             "DEVELOPMENT_PERIOD_DIAGNOSTIC" if available_at <= context["development_end"] else
             "POST_DEVELOPMENT_UNVALIDATED")
    return {
        "status": "INFERENCE_AVAILABLE", "recommendation":
            "FAVOUR_RESEARCH" if probability >= .5 and net_pct > 0 else "ABSTAIN",
        "probability_profit_raw": round(probability, 6),
        "expected_net_pct_raw": round(net_pct, 6),
        "prediction_uncalibrated": True, "time_scope": stage,
        "signal_available_at": available_at.isoformat().replace("+00:00", "Z"),
        "epoch": context["epoch"], "run_id": context["run_id"],
        "checkpoint_sha256": context["weights_sha256"],
        "snapshot_sha256": context["snapshot_sha256"],
        "feature_sha256": sha256(vector.tobytes()).hexdigest(),
        "model_schema": context["model_schema"],
        "candidate_direction": "LONG" if vector[5] > 0 else "SHORT",
        "guardian_authorised": False,
    }
