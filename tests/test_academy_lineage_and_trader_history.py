import csv
import tempfile
import unittest
from pathlib import Path
from research.academy_tower_lineage import AcademyCheckpoint, create_tower_population, population_manifest
from research.trader_history_import import import_trader_history, chronological_split


class AcademyLineageTests(unittest.TestCase):
    def test_sixteen_inherit_real_parent_identifiers(self):
        parent=AcademyCheckpoint("student-a","checkpoint-v3","a"*64,"skill-v1",True)
        agents=create_tower_population([parent])
        self.assertEqual(len(agents),16)
        self.assertTrue(all(a.parent_student_id=="student-a" for a in agents))
        self.assertTrue(all(a.parent_checkpoint_id=="checkpoint-v3" for a in agents))
        self.assertEqual(len({a.variant_seed for a in agents}),16)
        self.assertFalse(population_manifest(agents)["models_cloned"])

    def test_unqualified_parent_rejected(self):
        with self.assertRaises(ValueError):
            create_tower_population([AcademyCheckpoint("a","c","a"*64,"s")])


class TraderHistoryTests(unittest.TestCase):
    def test_import_and_purge_overlapping_trade(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"trades.csv"
            with path.open("w",newline="") as stream:
                writer=csv.writer(stream)
                writer.writerow(("trade_id","instrument","side","entry_utc","exit_utc","entry_price","exit_price","net_pnl"))
                for i in range(10):
                    exit_min=9 if i==6 else i+1
                    writer.writerow((str(i),"XAUUSD","BUY",f"2026-01-01T00:{i:02}:00Z",
                                     f"2026-01-01T00:{exit_min:02}:30Z",2000,2001,1 if i%2 else -1))
            dataset=import_trader_history(path,trader_id="example",source="authorized fixture",
                                          permission_reference="fixture-only",permitted_use="research training")
            split=chronological_split(dataset)
            self.assertEqual(len(split["holdout"]),3)
            self.assertEqual(split["purged_overlap"],1)
            self.assertFalse(dataset["permission_independently_verified"])

    def test_missing_permission_rejected(self):
        with self.assertRaises(ValueError):
            import_trader_history("missing.csv",trader_id="t",source="s",
                                  permission_reference="",permitted_use="research")


if __name__=="__main__":
    unittest.main()
