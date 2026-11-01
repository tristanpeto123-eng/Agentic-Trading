import csv
import tempfile
import unittest
from pathlib import Path
from research.dataset_evidence import dataset_manifest, heldout_report

PROVENANCE={"provider":"fixture","instrument":"XAUUSD","source_url":"https://example.org/fixture",
"retrieved_utc":"2026-11-01T00:00:00Z","license_reference":"test-only",
"permitted_use":"unit tests"}

class EvidenceTests(unittest.TestCase):
    def test_manifest_fingerprints_and_no_authorization(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=[]
            for side, offset in (("bid",0),("ask",1)):
                path=Path(folder)/(side+".csv")
                with path.open("w",newline="") as stream:
                    writer=csv.writer(stream)
                    writer.writerow(("timestamp","open","high","low","close"))
                    for i in range(3):
                        price=2000+i+offset
                        writer.writerow((f"2026-01-01T00:0{i}:00Z",price,price+1,price-1,price))
                paths.append(path)
            manifest=dataset_manifest(*paths,provenance=PROVENANCE)
            self.assertEqual(len(manifest["bid_sha256"]),64)
            self.assertNotEqual(manifest["bid_sha256"],manifest["ask_sha256"])
            self.assertFalse(manifest["license_verified"])

    def test_heldout_report(self):
        report=heldout_report([0]*20,train=8,validate=4,test=4)
        self.assertEqual(report["folds"][0]["test_start"],12)
        self.assertFalse(report["all_test_folds_positive"])
        self.assertFalse(report["execution_authorized"])

if __name__=="__main__":
    unittest.main()
