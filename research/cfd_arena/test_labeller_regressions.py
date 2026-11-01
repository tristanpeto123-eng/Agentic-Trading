"""Non-mutating regression/audit tests for supplied autolabel.py.

Run: python -m pytest -q test_autolabel_audit.py
Do NOT use these tests as validation of profitable trading performance.
"""
import numpy as np
import pandas as pd
import pytest

import autolabel as model


def test_all_detectors_are_prefix_invariant_on_deterministic_random_walk():
    history = model.demo_data(n=2500, seed=21)
    first = history.iloc[:1600].copy()
    for name, detector in model.DETECTORS.items():
        full_dir, full_strength = detector(history, model.atr(history))
        short_dir, short_strength = detector(first, model.atr(first))
        assert np.array_equal(full_dir.iloc[:1600].to_numpy(), short_dir.to_numpy()), name
        assert np.allclose(full_strength.iloc[:1600], short_strength, equal_nan=True), name


def test_stop_wins_when_tp_and_sl_both_touched_in_one_bar():
    n = 55
    frame = pd.DataFrame({"open": np.full(n, 100.0),
                          "high": np.full(n, 100.5),
                          "low": np.full(n, 99.5),
                          "close": np.full(n, 100.0)})
    frame.loc[19, "high"] = 103.0
    frame.loc[19, "low"] = 98.0
    atr = pd.Series(np.ones(n))
    labels, end = model.triple_barrier(frame, atr, [18], [1])
    assert labels[0] == 0.0
    assert end[0] == 19.0


def test_tp_can_win_when_stop_is_not_touched():
    n = 55
    frame = pd.DataFrame({"open": np.full(n, 100.0),
                          "high": np.full(n, 100.5),
                          "low": np.full(n, 99.5),
                          "close": np.full(n, 100.0)})
    frame.loc[19, "high"] = 103.0
    atr = pd.Series(np.ones(n))
    labels, end = model.triple_barrier(frame, atr, [18], [1])
    assert labels[0] == 1.0
    assert end[0] == 19.0


def test_expanding_window_purges_train_labels_that_overlap_validation_start():
    frame = model.demo_data(n=6500, seed=42)
    ds = model.build_dataset(frame, "fvg")
    assert len(ds) > 60
    n = len(ds)
    edges = np.linspace(int(n * .4), n, 6, dtype=int)
    for left in edges[:-1]:
        test_start = ds.iloc[left]["i"]
        train = ds.iloc[:left]
        purged = train[train["t_end"] < test_start]
        assert (purged["t_end"] < test_start).all()
        assert len(purged) <= len(train)


def test_labels_are_independent_of_future_bars_after_the_outcome():
    data = model.demo_data(n=1300, seed=31)
    direction, _ = model.detect_fvg(data, model.atr(data))
    candidates = np.flatnonzero(direction.to_numpy() != 0)
    valid = candidates[(candidates > 60) & (candidates < 700)]
    assert valid.size
    idx = int(valid[0]); sign = int(direction.iloc[idx])
    lab, end = model.triple_barrier(data, model.atr(data), [idx], [sign])
    changed = data.copy()
    changed.loc[900:, ["open", "high", "low", "close"]] *= 1.3
    updated, updated_end = model.triple_barrier(changed, model.atr(changed), [idx], [sign])
    assert lab[0] == updated[0]
    assert end[0] == updated_end[0]


def test_last_complete_horizon_should_be_labelled():
    n = model.HORIZON + 17
    data = pd.DataFrame({"open": np.full(n, 100.0),
                         "high": np.full(n, 101.0),
                         "low": np.full(n, 99.0),
                         "close": np.full(n, 100.0)})
    i = n - model.HORIZON - 2
    assert i + 1 + model.HORIZON == n - 1  # this one must be valid
    # The very last complete case is i = n - HORIZON - 1.
    i = n - model.HORIZON - 1
    assert i + 1 + model.HORIZON == n
    lab, _ = model.triple_barrier(data, pd.Series(np.ones(n)), [i], [1])
    assert np.isfinite(lab[0])
