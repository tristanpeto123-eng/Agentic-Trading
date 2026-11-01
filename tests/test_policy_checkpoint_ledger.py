import tempfile
import unittest
from pathlib import Path
from research.policy_checkpoint_ledger import CheckpointLedger
from research.walkforward_policy_gates import PolicyCandidate, GateError

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger=CheckpointLedger(Path(self.temp.name)/"checkpoints.json",
                                     frozen_skill_fingerprint="frozen")
        self.args={"baseline_net":0,"max_allowed_drawdown":3}

    def test_qualified_proposal_persists_without_promotion(self):
        result=self.ledger.propose(PolicyCandidate("v1","frozen",5,10,2),**self.args)
        self.assertEqual(result["state"],"proposed")
        saved=self.ledger.read()
        self.assertEqual(len(saved),1)
        self.assertFalse(saved[0]["ceo_approved"])
        self.assertFalse(saved[0]["execution_authorized"])

    def test_unqualified_does_not_write(self):
        result=self.ledger.propose(PolicyCandidate("v1","frozen",4,10,2),**self.args)
        self.assertFalse(result["qualified"])
        self.assertEqual(self.ledger.read(),[])

    def test_duplicate_version_rejected(self):
        candidate=PolicyCandidate("v1","frozen",5,10,2)
        self.ledger.propose(candidate,**self.args)
        with self.assertRaises(GateError):
            self.ledger.propose(candidate,**self.args)

if __name__=="__main__":
    unittest.main()
