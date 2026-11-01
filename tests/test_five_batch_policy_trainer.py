import unittest
from research.five_batch_policy_trainer import FiveBatchPolicyTrainer, TrainingError

class FiveBatchTrainerTests(unittest.TestCase):
    def test_checkpoint_every_five_batches(self):
        trainer=FiveBatchPolicyTrainer(("trend","range"))
        for index in range(4):
            self.assertIsNone(trainer.ingest_batch({"trend":2,"range":1}))
        snapshot=trainer.ingest_batch({"trend":2,"range":1},
                                      validation_rewards={"trend":-3,"range":9})
        self.assertEqual(snapshot.preferred_skill,"trend")
        self.assertEqual(snapshot.batches_seen,5)
        self.assertEqual(snapshot.validation_net,-3)
        self.assertEqual(len(trainer.snapshots),1)

    def test_no_early_validation(self):
        trainer=FiveBatchPolicyTrainer(("trend",))
        with self.assertRaises(TrainingError):
            trainer.ingest_batch({"trend":1},validation_rewards={"trend":1})
        self.assertEqual(len(trainer.batches),0)

    def test_missing_checkpoint_validation(self):
        trainer=FiveBatchPolicyTrainer(("trend",))
        for _ in range(4):
            trainer.ingest_batch({"trend":1})
        with self.assertRaises(TrainingError):
            trainer.ingest_batch({"trend":1})
        self.assertEqual(len(trainer.batches),4)

    def test_reject_skill_changes(self):
        trainer=FiveBatchPolicyTrainer(("trend","range"))
        with self.assertRaises(TrainingError):
            trainer.ingest_batch({"trend":1,"other":2})

if __name__=="__main__":
    unittest.main()
