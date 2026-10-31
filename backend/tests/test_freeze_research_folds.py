"""Offline folds: chronological partitioning is not qualification."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from freeze_research_folds import FoldError, freeze


def sample(tmp_path, n=1000):
    dest = tmp_path / 'candles.csv'
    when = datetime(2025, 1, 1, tzinfo=timezone.utc)
    lines = ['time,open,high,low,close']
    for i in range(n):
        stamp = when + timedelta(minutes=15 * i)
        lines.append(f'{stamp.isoformat()},100,103,99,101')
    dest.write_text('\n'.join(lines) + '\n')
    return dest


def test_folds_are_embargoed_sealed_deterministic(tmp_path):
    src = sample(tmp_path)
    result = freeze(src, embargo_bars=5, walk_folds=3, min_rows=10)
    assert freeze(src, embargo_bars=5, walk_folds=3, min_rows=10) == result
    assert result['train']['end_index_exclusive'] < result['development_validation']['start_index_inclusive']
    assert result['development_validation']['end_index_exclusive'] < result['sealed_final_test_boundary_metadata_only']['start_index_inclusive']
    for fold in result['training_only_walk_forward_folds']:
        assert fold['train']['end_index_exclusive'] + 10 <= fold['validation']['start_index_inclusive']
        assert fold['validation']['end_index_exclusive'] <= result['train']['end_index_exclusive']
    assert result['final_test_prices_exported'] is False
    assert result['data_source_and_rights_verified'] is False
    assert result['model_access_control_independently_verified'] is False
    assert result['independent_model_exam_performed'] is False
    assert not result['paper_eligible'] and not result['live_eligible']


def test_rejects_reversed_or_repeated_clock(tmp_path):
    src = sample(tmp_path)
    lines = src.read_text().splitlines()
    lines[3] = lines[2]
    src.write_text('\n'.join(lines) + '\n')
    with pytest.raises(FoldError, match='duplicate or out-of-order'):
        freeze(src, embargo_bars=5, min_rows=10)


def test_rejects_undersized_and_bad_ohlc(tmp_path):
    src = sample(tmp_path, n=50)
    with pytest.raises(FoldError, match='Insufficient rows'):
        freeze(src, embargo_bars=5, min_rows=10)
    src = sample(tmp_path)
    src.write_text(src.read_text().replace(',100,103,99,101', ',100,90,99,101', 1))
    with pytest.raises(FoldError, match='Invalid OHLC'):
        freeze(src, embargo_bars=5, min_rows=10)


def test_input_digest_changes_with_content(tmp_path):
    src = sample(tmp_path)
    previous = freeze(src, embargo_bars=5, min_rows=10)['input_sha256']
    src.write_text(src.read_text().replace(',100,103,99,101', ',100,104,99,101', 1))
    assert freeze(src, embargo_bars=5, min_rows=10)['input_sha256'] != previous
