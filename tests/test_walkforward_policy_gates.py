import unittest
from research.walkforward_policy_gates import (
    GateError, PolicyCandidate, policy_gate, walkforward_windows
)

class WalkforwardGateTests(unittest.TestCase):
    def test_chronological_disjoint_folds(self):
        windows=walkforward_windows(100,train=40,validate=20,test=10)
        self.assertGreater(len(windows),1)
        for w in windows:
            self.assertEqual(w.train[1],w.validate[0])
            self.assertEqual(w.validate[1],w.test[0])
            self.assertLessEqual(w.test[1],100)

    def test_insufficient_history(self):
        with self.assertRaises(GateError):
            walkforward_windows(10,train=8,validate=2,test=2)

    def test_five_batch_and_frozen_skill_gate(self):
        candidate=PolicyCandidate("v1","skills-hash",4,10,1)
        args=dict(baseline_net=0,max_allowed_drawdown=2,expected_fingerprint="skills-hash")
        self.assertFalse(policy_gate(candidate,**args)["qualified"])
        candidate=PolicyCandidate("v1","changed",5,10,1)
        self.assertFalse(policy_gate(candidate,**args)["qualified"])
        candidate=PolicyCandidate("v1","skills-hash",5,10,1)
        result=policy_gate(candidate,**args)
        self.assertTrue(result["qualified"])
        self.assertFalse(result["execution_authorized"])

    def test_reject_drawdown_or_no_improvement(self):
        args=dict(baseline_net=0,max_allowed_drawdown=2,expected_fingerprint="frozen")
        self.assertFalse(policy_gate(PolicyCandidate("v1","frozen",5,10,3),**args)["qualified"])
        self.assertFalse(policy_gate(PolicyCandidate("v1","frozen",5,-1,1),**args)["qualified"])

if __name__=="__main__":
    unittest.main()
