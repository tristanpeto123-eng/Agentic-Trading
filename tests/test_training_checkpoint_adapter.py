import tempfile
import unittest
from pathlib import Path
from research.policy_checkpoint_ledger import CheckpointLedger
from research.training_checkpoint_adapter import propose_training_snapshot
from research.walkforward_policy_gates import GateError

class Snapshot:
    version=1
    batches_seen=5
    skill_fingerprint="frozen"
    validation_net=4.0

class AdapterTests(unittest.TestCase):
    def test_proposal_is_not_execution_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=CheckpointLedger(Path(directory)/"ledger.json",frozen_skill_fingerprint="frozen")
            result=propose_training_snapshot(ledger,Snapshot(),validation_max_drawdown=1,
                                             baseline_net=0,max_allowed_drawdown=2)
            self.assertTrue(result["qualified"])
            self.assertFalse(ledger.read()[0]["execution_authorized"])
            self.assertFalse(ledger.read()[0]["ceo_approved"])

    def test_wrong_fingerprint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=CheckpointLedger(Path(directory)/"ledger.json",frozen_skill_fingerprint="different")
            result=propose_training_snapshot(ledger,Snapshot(),validation_max_drawdown=1,
                                             baseline_net=0,max_allowed_drawdown=2)
            self.assertFalse(result["qualified"])
            self.assertEqual(ledger.read(),[])

if __name__=="__main__":
    unittest.main()
