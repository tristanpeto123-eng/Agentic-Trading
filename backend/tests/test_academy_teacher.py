import unittest
from agentic_trading.academy_teacher import predict_academy_teacher
from agentic_trading.neural_training import FEATURE_NAMES, TrainingError

class TeacherInferenceTests(unittest.TestCase):
    def test_rejects_wrong_feature_schema(self):
        with self.assertRaises(TrainingError):
            predict_academy_teacher(None,[0.0]*6)

    def test_real_model_inference_is_not_trade_action(self):
        try:
            import torch
        except ImportError:
            self.skipTest("torch optional")
        from agentic_trading.neural_training import _model
        model=_model(torch)
        result=predict_academy_teacher(model,[0.0]*len(FEATURE_NAMES))
        self.assertTrue(0<=result["profitability_estimate"]<=1)
        self.assertFalse(result["is_trade_action"])
        self.assertTrue(result["research_only"])

if __name__=="__main__":
    unittest.main()
