"""Immutable source-file fingerprints and conservative research evaluation reports."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from .data_qualification import QualificationError
from .pair_qualification import qualify_pair
from .walkforward_policy_gates import walkforward_windows


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_manifest(bid_path: str | Path, ask_path: str | Path, *,
                     provenance: dict, expected_seconds: int = 60) -> dict:
    qualified = qualify_pair(bid_path, ask_path, provenance=provenance,
                             expected_seconds=expected_seconds)
    return {"schema_version": 1, "bid_sha256": file_sha256(bid_path),
            "ask_sha256": file_sha256(ask_path),
            "candles": qualified["candles"],
            "max_observed_spread": qualified["max_observed_spread"],
            "provenance": provenance,
            "license_verified": False,
            "execution_authorized": False}


def heldout_report(net_results: list[float], *, train: int, validate: int,
                   test: int) -> dict:
    """Partition chronological per-candle net outcomes; no fitted model involved.

    This is descriptive evaluation infrastructure, not statistical proof of alpha.
    """
    if any(not isinstance(x, (float, int)) or not math.isfinite(x)
           for x in net_results):
        raise QualificationError("nonfinite outcomes")
    windows = walkforward_windows(len(net_results), train=train,
                                  validate=validate, test=test)
    folds = []
    for window in windows:
        values = net_results[window.test[0]:window.test[1]]
        equity = peak = drawdown = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        folds.append({"test_start": window.test[0],
                      "test_end": window.test[1],
                      "net": equity, "max_drawdown": drawdown})
    return {"folds": folds, "all_test_folds_positive": all(f["net"] > 0 for f in folds),
            "license_verified": False, "execution_authorized": False,
            "warning": "Descriptive only; overlapping folds are not independent and no alpha is established."}
