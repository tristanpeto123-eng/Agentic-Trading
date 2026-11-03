import csv
import tempfile
import unittest
from pathlib import Path
from research.offline_replay_cli import evaluate
from research.data_qualification import QualificationError

PROVENANCE={"provider":"fixture","instrument":"XAUUSD","source_url":"https://example.org/fixture",
"retrieved_utc":"2026-11-01T00:00:00Z","license_reference":"unit-test-only",
"permitted_use":"synthetic test fixtures"}

class OfflineReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths=[]
        for side, offset in (("bid",0),("ask",0.5)):
            path=Path(self.tmp.name)/(side+".csv")
            with path.open("w",newline="") as stream:
                writer=csv.writer(stream)
                writer.writerow(("timestamp","open","high","low","close"))
                for i in range(20):
                    price=2000+i+offset
                    writer.writerow((f"2026-01-01T00:{i:02}:00Z",price,price+1,price-1,price))
            self.paths.append(path)

    def test_disjoint_holdout_and_no_authorization(self):
        result=evaluate(*self.paths,PROVENANCE,fee=0.1,slippage=0.1)
        self.assertEqual(result["holdout_start_index"],15)
        self.assertEqual(result["training"]["trades"],12)
        self.assertEqual(result["holdout"]["trades"],3)
        self.assertFalse(result["license_verified"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(len(result["manifest"]["bid_sha256"]),64)

    def test_reject_invalid_holdout(self):
        with self.assertRaises(QualificationError):
            evaluate(*self.paths,PROVENANCE,holdout_fraction=1)

if __name__=="__main__":
    unittest.main()
