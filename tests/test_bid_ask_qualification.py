"""Offline regression tests for BID/ASK structural qualification."""
import csv
import tempfile
import unittest
from pathlib import Path
from research.data_qualification import QualificationError, qualify_csv
from research.pair_qualification import qualify_pair

PROVENANCE = {"provider":"example","instrument":"XAUUSD","source_url":"https://example.org/data",
"retrieved_utc":"2026-11-01T00:00:00Z","license_reference":"unverified",
"permitted_use":"research pending legal review"}

class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, values):
        path = Path(self.tmp.name) / name
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp","open","high","low","close"])
            for time, price in values:
                writer.writerow([time, price, price+1, price-1, price])
        return path

    def test_valid_pair_remains_unlicensed(self):
        bid = self.write("bid.csv",[("2026-01-01T00:00:00Z",2000),("2026-01-01T00:01:00Z",2001)])
        ask = self.write("ask.csv",[("2026-01-01T00:00:00Z",2000.5),("2026-01-01T00:01:00Z",2001.5)])
        result = qualify_pair(bid,ask,provenance=PROVENANCE)
        self.assertEqual(result["candles"],2)
        self.assertFalse(result["license_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_mismatched_timestamps(self):
        bid = self.write("bid.csv",[("2026-01-01T00:00:00Z",2000),("2026-01-01T00:01:00Z",2001)])
        ask = self.write("ask.csv",[("2026-01-01T00:01:00Z",2000.5),("2026-01-01T00:02:00Z",2001.5)])
        with self.assertRaisesRegex(QualificationError,"timestamp mismatch"):
            qualify_pair(bid,ask,provenance=PROVENANCE)

    def test_crossed_quotes(self):
        bid = self.write("bid.csv",[("2026-01-01T00:00:00Z",2000),("2026-01-01T00:01:00Z",2001)])
        ask = self.write("ask.csv",[("2026-01-01T00:00:00Z",1999),("2026-01-01T00:01:00Z",2000)])
        with self.assertRaisesRegex(QualificationError,"crossed"):
            qualify_pair(bid,ask,provenance=PROVENANCE)

    def test_gap(self):
        path = self.write("gap.csv",[("2026-01-01T00:00:00Z",2000),("2026-01-01T00:02:00Z",2001)])
        with self.assertRaisesRegex(QualificationError,"non-contiguous"):
            qualify_csv(path,side="BID")

    def test_missing_provenance(self):
        with self.assertRaisesRegex(QualificationError,"provenance"):
            qualify_pair("missing","missing",provenance={})

if __name__ == "__main__":
    unittest.main()
