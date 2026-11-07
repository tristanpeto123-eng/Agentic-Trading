import unittest
from agentic_trading.academy_tower_bridge import create_academy_seeded_tower
from agentic_trading.evolution_tower import advance_state, TowerError

class AcademyTowerBridgeTests(unittest.TestCase):
    def test_population_reaches_existing_simulator(self):
        checkpoint={"student_id":"student-a","checkpoint_id":"cp-1",
                    "model_sha256":"a"*64,"qualification":"research_qualified"}
        state=create_academy_seeded_tower([checkpoint])
        self.assertEqual(len(state["population"]),16)
        self.assertTrue(all(a["academy_parent_student_id"]=="student-a" for a in state["population"]))
        self.assertTrue(all(a["academy_weights_inherited"] is False for a in state["population"]))
        self.assertFalse(state["paper_trading_enabled"])
        advanced,events=advance_state(state)
        self.assertEqual(advanced["generation"],1)

    def test_unqualified_blocked(self):
        with self.assertRaises(TowerError):
            create_academy_seeded_tower([{"qualification":"unqualified"}])

if __name__=="__main__":
    unittest.main()
