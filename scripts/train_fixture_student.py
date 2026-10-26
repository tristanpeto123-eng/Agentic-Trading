#!/usr/bin/env python3
"""Explicitly authorised local S6 synthetic fixture trainer. Never suitable for production."""
import argparse
from datetime import datetime
from pathlib import Path

from agentic_trading.neural_training import TrainingSettings, run_fixture_training
from agentic_trading.settings import Settings
from agentic_trading.storage import new_session_factory


def main():
    parser = argparse.ArgumentParser(description='Offline experimental fixture MLP (NO qualification)')
    parser.add_argument('--student', required=True, help='Existing student UUID')
    parser.add_argument('--market', default='XAUUSD')
    parser.add_argument('--tactic', default='trend')
    parser.add_argument('--as-of', required=True, help='UTC ISO8601 cutoff such as 2025-06-01T00:00:00+00:00')
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dev-fixtures', action='store_true', required=True,
                        help='Explicitly authorize synthetic development-only training')
    args = parser.parse_args()
    config = Settings.from_env()
    if config.environment != 'development':
        parser.error('training fixtures are forbidden outside the development environment')
    payload = TrainingSettings(args.student, args.market, args.tactic,
                               datetime.fromisoformat(args.as_of.replace('Z', '+00:00')),
                               seed=args.seed, epochs=args.epochs)
    engine, factory = new_session_factory(config.database_url)
    try:
        with factory() as session:
            result = run_fixture_training(session, Path(config.data_dir or 'data_store'), payload,
                                          environment=config.environment,
                                          explicit_fixture_authorisation=args.dev_fixtures)
            print('Experiment:', result['experiment_key'])
            print('Epochs:', result['epochs_completed'], '· train:', result['train_examples'],
                  '· validation:', result['validation_examples'])
            print('UNQUALIFIED: no broker trading, qualification or real-data eligibility')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
