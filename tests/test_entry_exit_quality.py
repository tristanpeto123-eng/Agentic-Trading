"""No-lookahead, no-trade, cost, embargo and sealed-test research checks."""
from datetime import datetime, timedelta, timezone
import csv
from pathlib import Path
import tempfile
import unittest

from research.entry_exit_quality import EntryExitPlan, evaluate_entry_exit_candidates
from research.data_qualification import QualificationError


PROVENANCE = {
    "provider": "local-synthetic-unit-fixture",
    "instrument": "XAUUSD",
    "source_url": "https://example.org/not-a-real-data-provider",
    "retrieved_utc": "2026-11-02T00:00:00Z",
    "license_reference": "UNIT-TEST-ONLY",
    "permitted_use": "generated synthetic testing only",
}


def fixture(folder: Path, *, mode: str, tamper: str | None = None, length: int = 240):
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    paths = []
    for side, spread in (("bid", 0.0), ("ask", 1.0)):
        p = folder / f"{side}.csv"
        with p.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("timestamp", "open", "high", "low", "close"))
            for i in range(length):
                if mode == "trend":
                    price = 2000.0 + i * 2.0
                elif mode == "flat":
                    price = 2000.0
                else:
                    raise AssertionError(mode)
                if tamper == "development" and i >= length * 70 // 100:
                    price += ((i % 2) * 300.0)
                if tamper == "terminal" and i >= length * 80 // 100:
                    price += 500.0 + (i % 3)
                at = stamp + timedelta(minutes=i + (1 if tamper == "gap" and i >= 30 else 0))
                o = price + spread
                writer.writerow((at.isoformat().replace("+00:00", "Z"), o, o + 1.0, o - 1.0, o))
        paths.append(p)
    return paths


class EntryExitQualityTests(unittest.TestCase):
    def test_trend_selection_uses_after_cost_net_and_next_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            bid, ask = fixture(Path(tmp), mode="trend")
            r = evaluate_entry_exit_candidates(bid, ask, provenance=PROVENANCE)
            self.assertEqual(r["train_selected"]["rule"], "MOMENTUM")
            self.assertGreater(r["development_selected"]["trades"], 0)
            self.assertGreater(r["development_selected"]["net"], 0)
            self.assertEqual(r["training_cash_baseline"]["net"], 0)
            self.assertGreater(r["development_selected"]["friction"], 0)
            self.assertEqual(len(r["train_candidates"]), 8)
            self.assertFalse(r["sealed_terminal_evaluated"])
            self.assertFalse(r["strategy_qualified"])
            self.assertFalse(r["license_verified"])
            self.assertFalse(r["paper_trading_enabled"])
            self.assertFalse(r["live_trading_enabled"])
            sample = r["development_selected"]["samples"][0]
            self.assertGreater(sample["entry_utc"], sample["signal_utc"])
            self.assertGreater(sample["exit_utc"], sample["entry_utc"])
            self.assertEqual(sample["execution_basis"], "NEXT_OPEN_QUOTE_PROXY_NOT_EXECUTABLE_TICK")

    def test_flat_market_abstains_and_is_not_called_profitable(self):
        with tempfile.TemporaryDirectory() as tmp:
            bid, ask = fixture(Path(tmp), mode="flat")
            r = evaluate_entry_exit_candidates(bid, ask, provenance=PROVENANCE)
            self.assertEqual(r["train_selected"]["rule"], "NO_TRADE")
            self.assertEqual(r["development_selected"]["trades"], 0)
            self.assertEqual(r["development_selected"]["net"], 0)
            self.assertTrue(r["development_selected"]["inactivity_is_not_profitability"])
            self.assertFalse(any(x["eligible_over_no_trade"] for x in r["train_candidates"]))

    def test_development_and_sealed_prices_cannot_choose_training_winner(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            a = fixture(Path(tmp1), mode="trend")
            b = fixture(Path(tmp2), mode="trend", tamper="development")
            x = evaluate_entry_exit_candidates(*a, provenance=PROVENANCE)
            y = evaluate_entry_exit_candidates(*b, provenance=PROVENANCE)
            self.assertEqual(x["train_selected"], y["train_selected"])
            self.assertEqual(x["train_candidates"], y["train_candidates"])
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            a = fixture(Path(tmp1), mode="trend")
            b = fixture(Path(tmp2), mode="trend", tamper="terminal")
            x = evaluate_entry_exit_candidates(*a, provenance=PROVENANCE)
            y = evaluate_entry_exit_candidates(*b, provenance=PROVENANCE)
            self.assertEqual(x["train_selected"], y["train_selected"])
            self.assertEqual(x["development_selected"], y["development_selected"])
            self.assertNotEqual(x["full_pair_identity_sha256"], y["full_pair_identity_sha256"])

    def test_unchanged_inputs_yield_unchanged_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            bid, ask = fixture(Path(tmp), mode="trend")
            x = evaluate_entry_exit_candidates(bid, ask, provenance=PROVENANCE)
            y = evaluate_entry_exit_candidates(bid, ask, provenance=PROVENANCE)
            self.assertEqual(x, y)
            self.assertEqual(len(x["report_sha256"]), 64)
            self.assertLessEqual(x["partitions"]["train"][1], x["partitions"]["embargo"][0])
            self.assertLessEqual(x["partitions"]["embargo"][1], x["partitions"]["development"][0])
            self.assertEqual(x["partitions"]["development"][1], x["partitions"]["sealed_terminal_uninspected"][0])

    def test_non_contiguous_and_unattested_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bid, ask = fixture(Path(tmp), mode="trend", tamper="gap")
            with self.assertRaises(QualificationError):
                evaluate_entry_exit_candidates(bid, ask, provenance=PROVENANCE)
        with tempfile.TemporaryDirectory() as tmp:
            bid, ask = fixture(Path(tmp), mode="trend")
            with self.assertRaises(QualificationError):
                evaluate_entry_exit_candidates(bid, ask, provenance={})

    def test_invalid_risk_plan_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bid, ask = fixture(Path(tmp), mode="trend")
            for plan in (EntryExitPlan(quantity=10),
                         EntryExitPlan(slippage_per_side=-1),
                         EntryExitPlan(holding=0),
                         EntryExitPlan(latency=0),
                         EntryExitPlan(lookback=True),
                         EntryExitPlan(min_training_trades=0)):
                with self.subTest(plan=plan):
                    with self.assertRaises(QualificationError):
                        evaluate_entry_exit_candidates(bid, ask, provenance=PROVENANCE, plan=plan)


if __name__ == "__main__":
    unittest.main()
