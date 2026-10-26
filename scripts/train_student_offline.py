#!/usr/bin/env python3
"""Run one bounded S6 offline research job; NEVER trades, promotes, or activates bots.

Requires a pre-created student/plan and closed S5 TRAIN-only research memories.
Examples/weights/checkpoints are local/private; no credentials, datasets or weights
are written to source control. To resume pass the SAME run-id and exact settings.
"""
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from uuid import UUID
import json

from agentic_trading.neural_training import TrainingSpec, train_student
from agentic_trading.settings import Settings
from agentic_trading.storage import new_session_factory


def main():
    p = ArgumentParser(description='Offline, research-only student neural training (Sprint 6)')
    p.add_argument('--student-id', required=True, type=UUID)
    p.add_argument('--run-id', required=True, type=UUID)
    p.add_argument('--as-of', required=True, help='ISO8601 UTC timestamp (+00:00)')
    p.add_argument('--plan-version', required=True, type=int)
    p.add_argument('--market', default='XAUUSD')
    p.add_argument('--tactic', default='trend')
    p.add_argument('--epochs', type=int, default=12)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--learning-rate', type=float, default=0.01)
    p.add_argument('--stop-after-epoch', type=int, default=None)
    p.add_argument('--checkpoint-root', type=Path, default=Path('model_store'))
    args = p.parse_args()
    spec = TrainingSpec(run_id=args.run_id, student_id=args.student_id, as_of=datetime.fromisoformat(args.as_of),
        plan_version=args.plan_version, market=args.market, tactic=args.tactic,
        epochs=args.epochs, seed=args.seed, learning_rate=args.learning_rate)
    engine, factory = new_session_factory(Settings.from_env().database_url)
    try:
        with factory() as session:
            result = train_student(session, spec, checkpoint_root=args.checkpoint_root,
                                   stop_after_epoch=args.stop_after_epoch)
        print(json.dumps(result, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
