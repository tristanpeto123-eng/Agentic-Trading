import tempfile
import csv
from datetime import datetime, timedelta, timezone
import unittest
from pathlib import Path
from unittest.mock import patch

from research.autonomous_research_simulation import _signals, _score, _pass, run


class AutonomousResearchTests(unittest.TestCase):
    def test_real_csv_pipeline_keeps_costly_flat_fixture_unqualified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            for side, offset in (("bid", 0), ("ask", 1)):
                with (root / f"{side}.csv").open("w", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(("timestamp", "open", "high", "low", "close"))
                    for minute in range(1800):
                        price = 2000 + offset
                        writer.writerow(((start + timedelta(minutes=minute)).isoformat(),
                                         price, price + 1, price - 1, price))
            provenance = {
                "provider": "fixture", "instrument": "XAUUSD",
                "source_url": "https://example.org/fixture",
                "retrieved_utc": "2026-11-14T00:00:00Z",
                "license_reference": "synthetic-test-only", "permitted_use": "unit testing",
            }
            result = run(root / "bid.csv", root / "ask.csv", provenance,
                         output=root / "report.json", fee=1, slippage=0.25,
                         max_generations=1, min_trades=100)
            self.assertEqual(result["status"], "research_failed")
            self.assertEqual(result["dataset_manifest"]["candles"], 1800)
            self.assertTrue(all(not window["passed"] for window in result["sealed_evaluation"]))
            self.assertFalse(result["license_verified"])
            self.assertFalse(result["checkpoint"]["execution_authorized"])
            self.assertFalse(result["checkpoint"]["promoted"])

    def test_no_lookahead_and_boundaries(self):
        closes = [1, 2, 3, 2, 1, 4, 5, 6]
        self.assertEqual(_signals(closes, "momentum", 2, 6), [0, 0, 1, -1, 0, 0, 0, 0])
        self.assertEqual(_signals(closes, "flat", 2, 6), [0] * 8)

    def test_costed_risk_and_profit_gate(self):
        records = [{"net": x} for x in (3, -1, 3, -1)]
        m = _score(records, 100, 10)
        self.assertTrue(_pass(m, 4, 1.3, 10))
        self.assertFalse(_pass(m, 100, 1.3, 10))
        self.assertTrue(_score([{"net": -12}], 100, 10)["risk_stopped"])

    def test_risk_stop_excludes_unscored_future_replay_trades(self):
        # The offline replay has already generated both records. An evaluation
        # drawdown stop must not count hypothetical recovery after the breach.
        records = [{"net": -12.0}, {"net": 1000.0}]
        metrics = _score(records, 100.0, 10.0)
        self.assertTrue(metrics["risk_stopped"])
        self.assertEqual(metrics["trades"], 1)
        self.assertEqual(metrics["replayed_trades"], 2)
        self.assertEqual(metrics["net"], -12.0)
        self.assertTrue(metrics["risk_stop_scoring_only"])
        self.assertFalse(_pass(metrics, 1, 1.3, 10.0))

    def test_no_trade_evaluation_does_not_qualify(self):
        metrics = _score([], 100.0, 10.0)
        self.assertEqual(metrics["trades"], 0)
        self.assertEqual(metrics["replayed_trades"], 0)
        self.assertFalse(metrics["risk_stopped"])
        self.assertFalse(_pass(metrics, 1, 1.3, 10.0))

    def test_reject_insufficient_holdout(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("research.autonomous_research_simulation.dataset_manifest", return_value={"digest": "test"}), patch(
                "research.autonomous_research_simulation._rows", return_value=iter([(None, 0, 0, 0, 1)] * 80)
            ):
                with self.assertRaisesRegex(ValueError, "insufficient independent test"):
                    run("bid.csv", "ask.csv", {}, output=str(Path(d) / "out.json"),
                        fee=0, slippage=0, max_generations=1)

    def test_frozen_holdout_not_reused_for_training(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            def fake_replay(bid, ask, signals, **kwargs):
                active = [i for i, s in enumerate(signals) if s]
                calls.append(active)
                return {"trade_records": [{"net": 2.0} for _ in active]}
            rows = [(None, 0, 0, 0, float(i)) for i in range(1800)]
            with patch("research.autonomous_research_simulation.dataset_manifest", return_value={"digest": "test"}), patch(
                "research.autonomous_research_simulation._rows", return_value=iter(rows)
            ), patch("research.autonomous_research_simulation.replay_signals", side_effect=fake_replay):
                result = run("bid.csv", "ask.csv", {}, output=str(Path(d) / "out.json"),
                             fee=1, slippage=1, max_generations=2, min_trades=100)
            self.assertEqual(result["policy"]["batches_seen"], 10)
            self.assertFalse(result["checkpoint"]["ceo_approved"])
            self.assertFalse(result["checkpoint"]["execution_authorized"])
            self.assertFalse(result["holdout_used_for_training"])
            self.assertEqual(len(result["sealed_evaluation"]), 3)
            # Each test window is read only once for the frozen selected skill.
            self.assertEqual(sum(bool(c and min(c) >= 1350) for c in calls), 3)
            self.assertTrue((Path(d) / "out.json").exists())


if __name__ == "__main__":
    unittest.main()
