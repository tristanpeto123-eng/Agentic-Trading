"""Synthetic unit fixtures: not a claim of trading performance."""
import csv
import tempfile
import unittest
from pathlib import Path
from research.costed_bid_ask_replay import replay_signals
from research.data_qualification import QualificationError

PROVENANCE = {"provider":"fixture","instrument":"XAUUSD","source_url":"https://example.org/fixture",
"retrieved_utc":"2026-11-01T00:00:00Z","license_reference":"synthetic-test-only",
"permitted_use":"unit testing"}

class CostedReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for side, offset in (("bid",0),("ask",1)):
            with (Path(self.tmp.name)/(side+".csv")).open("w",newline="") as f:
                writer=csv.writer(f)
                writer.writerow(("timestamp","open","high","low","close"))
                for i in range(4):
                    price=2000+i*2+offset
                    writer.writerow((f"2026-01-01T00:0{i}:00Z",price,price+1,price-1,price))
        self.bid=Path(self.tmp.name)/"bid.csv"
        self.ask=Path(self.tmp.name)/"ask.csv"

    def test_next_open_and_costs(self):
        result=replay_signals(self.bid,self.ask,[1,0,0,0],
                              provenance=PROVENANCE,fee_per_round_trip=0.5,
                              slippage_per_side=0.25)
        self.assertEqual(result["trades"],1)
        self.assertAlmostEqual(result["net_per_unit"],0)
        self.assertFalse(result["execution_authorized"])

    def test_no_lookahead_for_last_two_signals(self):
        result=replay_signals(self.bid,self.ask,[0,0,1,1],provenance=PROVENANCE)
        self.assertEqual(result["trades"],0)

    def test_reject_negative_costs(self):
        with self.assertRaises(QualificationError):
            replay_signals(self.bid,self.ask,[0]*4,provenance=PROVENANCE,
                           slippage_per_side=-1)

    def test_reject_signal_mismatch(self):
        with self.assertRaises(QualificationError):
            replay_signals(self.bid,self.ask,[1],provenance=PROVENANCE)

if __name__=="__main__":
    unittest.main()
