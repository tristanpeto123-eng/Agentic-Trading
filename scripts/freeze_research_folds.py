#!/usr/bin/env python3
"""Create immutable, research-only chronological split manifests from local OHLC CSV.

No provider authentication, rights validation, model training or trading. Raw
prices stay local; the final test rows are not exported by this tool.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path


class FoldError(ValueError):
    pass


def _clock(value: str, minutes: int) -> datetime:
    try:
        at = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except (TypeError, ValueError) as exc:
        raise FoldError('Invalid timestamp') from exc
    if at.tzinfo is None or at.utcoffset() != timedelta(0):
        raise FoldError('Timestamp must be UTC')
    if at.second or at.microsecond or (at.hour * 60 + at.minute) % minutes:
        raise FoldError('Timestamp not aligned to declared interval')
    return at


def _prices(row: dict, fields: list[str]) -> None:
    try:
        numbers = [Decimal(row[field]) for field in fields]
    except (TypeError, KeyError, InvalidOperation, ValueError) as exc:
        raise FoldError('Invalid OHLC price') from exc
    op, hi, lo, cl = numbers
    if not all(x.is_finite() and x > 0 for x in numbers) or hi < max(op, cl) or lo > min(op, cl) or lo > hi:
        raise FoldError('Invalid OHLC bounds or non-positive prices')


def _boundary(stamps: list[datetime], start: int, stop: int) -> dict:
    if not (0 <= start < stop <= len(stamps)):
        raise FoldError('Insufficient rows for nonempty fold')
    return {'start_index_inclusive': start, 'end_index_exclusive': stop,
            'first_open_utc': stamps[start].isoformat(),
            'last_open_utc': stamps[stop - 1].isoformat(), 'rows': stop - start}


def freeze(csv_path: Path, *, interval_minutes: int = 15, embargo_bars: int = 96,
           walk_folds: int = 3, min_rows: int = 100, data_limit_bytes: int = 100_000_000) -> dict:
    """Hash original bytes and partition by observed rows, without gap-filling.

    Nested walk-forward windows are inside training only. A separate model
    runner must enforce access isolation and establish a sufficient embargo
    for its actual feature/label lookahead.
    """
    if interval_minutes not in (1, 5, 15, 60, 240):
        raise FoldError('Unsupported OHLC interval')
    if embargo_bars < 1 or not (1 <= walk_folds <= 8) or min_rows < 2:
        raise FoldError('Invalid fold configuration')
    if not csv_path.is_file() or csv_path.stat().st_size > data_limit_bytes:
        raise FoldError('CSV missing or oversized')
    raw = csv_path.read_bytes()
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeError as exc:
        raise FoldError('CSV must be UTF-8') from exc
    reader = csv.DictReader(content.splitlines())
    if reader.fieldnames not in (
        ['time', 'open', 'high', 'low', 'close'],
        ['timestamp_open', 'open', 'high', 'low', 'close', 'volume'],
        ['Etc/UTC', 'Open', 'High', 'Low', 'Close', 'Volume'],
        ['time', 'open', 'high', 'low', 'close', 'volume'],
    ):
        raise FoldError('Unexpected OHLC CSV schema')
    stamps = []
    previous = None
    gaps = 0
    for row_number, row in enumerate(reader, 2):
        try:
            stamp = _clock(row[reader.fieldnames[0]], interval_minutes)
            _prices(row, reader.fieldnames[1:5])
            if reader.fieldnames[-1].lower() == 'volume':
                volume = Decimal(row[reader.fieldnames[-1]])
                if not volume.is_finite() or volume < 0:
                    raise FoldError('Invalid volume')
        except (FoldError, InvalidOperation, TypeError, KeyError) as exc:
            raise FoldError(f'Row {row_number}: {exc}') from exc
        if previous is not None:
            if stamp <= previous:
                raise FoldError(f'Row {row_number}: duplicate or out-of-order timestamp')
            if stamp - previous > timedelta(minutes=interval_minutes):
                gaps += 1
        previous = stamp
        stamps.append(stamp)
    n = len(stamps)
    train_boundary = n * 60 // 100
    test_boundary = n * 80 // 100
    e = embargo_bars
    train = _boundary(stamps, 0, train_boundary - e)
    validation = _boundary(stamps, train_boundary + e, test_boundary - e)
    test = _boundary(stamps, test_boundary + e, n)
    if min(x['rows'] for x in (train, validation, test)) < min_rows:
        raise FoldError('Insufficient rows for embargoed holdout')
    training_limit = train_boundary - e
    first_split = training_limit * 35 // 100
    step = (training_limit - first_split) // walk_folds
    wf = []
    for i in range(walk_folds):
        split = first_split + i * step
        end = first_split + (i + 1) * step if i < walk_folds - 1 else training_limit
        lookback = _boundary(stamps, 0, split - e)
        next_window = _boundary(stamps, split + e, end)
        if min(lookback['rows'], next_window['rows']) < min_rows:
            raise FoldError('Insufficient rows for walk-forward training folds')
        wf.append({'fold': i + 1, 'train': lookback, 'validation': next_window})
    manifest = {
        'schema': 'xauusd_offline_holdout_manifest.v1',
        'input_sha256': hashlib.sha256(raw).hexdigest(),
        'instrument_claim': 'XAUUSD (NOT independently attested)',
        'quote_basis_claim': 'OHLC candles (NOT executable tick BID/ASK)',
        'interval_minutes': interval_minutes, 'total_rows': n,
        'first_open_utc': stamps[0].isoformat(), 'last_open_utc': stamps[-1].isoformat(),
        'observed_gap_count': gaps, 'unverified_session_calendar': True,
        'embargo_bars_each_side': embargo_bars,
        'minimum_required_embargo_must_cover_all_feature_and_label_lookahead': True,
        'train': train, 'development_validation': validation,
        'sealed_final_test_boundary_metadata_only': test,
        'training_only_walk_forward_folds': wf,
        'final_test_prices_exported': False,
        'model_access_control_independently_verified': False,
        'data_source_and_rights_verified': False,
        'independent_model_exam_performed': False,
        'research_only': True, 'paper_eligible': False, 'live_eligible': False,
    }
    manifest['manifest_sha256'] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--minutes', type=int, default=15)
    parser.add_argument('--embargo', type=int, default=96)
    parser.add_argument('--folds', type=int, default=3)
    parser.add_argument('--minimum', type=int, default=100)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = freeze(args.csv, interval_minutes=args.minutes,
                        embargo_bars=args.embargo, walk_folds=args.folds, min_rows=args.minimum)
        rendered = json.dumps(report, sort_keys=True, indent=2) + '\n'
        if args.output:
            args.output.write_text(rendered, encoding='utf-8')
        else:
            print(rendered, end='')
    except (FoldError, OSError) as exc:
        parser.exit(2, f'Holdout manifest rejected: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
