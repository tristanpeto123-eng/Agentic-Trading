from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from agentic_trading.chronological_holdout import split_chronological

T = datetime(2025, 1, 1, tzinfo=timezone.utc)


def candles(n=1000):
    return [SimpleNamespace(open_time=T+timedelta(minutes=15*i),
                            open="4000", high="4002", low="3998", close="4001",
                            volume=None) for i in range(n)]


def test_three_folds_are_ordered_disjoint_and_embargoed():
    bars = candles()
    split = split_chronological(bars, embargo_bars=10, minimum_per_fold=100)
    assert split.counts == {"train": 590, "validation": 180, "test": 190, "embargoed": 40}
    assert split.train[-1].open_time < split.validation[0].open_time
    assert split.validation[-1].open_time < split.test[0].open_time
    assert split.manifest_sha256 == split_chronological(candles(), embargo_bars=10,
                                                        minimum_per_fold=100).manifest_sha256
    assert split.research_only and not split.qualified


def test_fail_closed_on_small_or_unsorted_data():
    with pytest.raises(ValueError, match="Not enough rows"):
        split_chronological(candles(100), embargo_bars=10, minimum_per_fold=50)
    rows = candles(1000)
    rows[5].open_time = rows[4].open_time
    with pytest.raises(ValueError, match="strictly chronological"):
        split_chronological(rows, embargo_bars=10, minimum_per_fold=100)
    with pytest.raises(ValueError, match="positive"):
        split_chronological(candles(), embargo_bars=0)
