import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.domain.lts_rules import BikePathAnalysis


class TestLtsRules(unittest.TestCase):
    def test_biking_permitted_marks_motorway_not_allowed(self):
        edges = pd.DataFrame(
            {
                "bicycle": ["yes", "yes"],
                "access": ["yes", "yes"],
                "highway": ["residential", "motorway"],
            }
        )

        allowed, not_allowed = BikePathAnalysis.biking_permitted(edges)
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(not_allowed), 1)
        self.assertEqual(not_allowed.iloc[0]["rule"], "p3")

    def test_slope_penalty_increases_lts_for_hard_long_urban_edge(self):
        edges = pd.DataFrame(
            {
                "context": ["urban"],
                "slope_class": ["8-10: hard"],
                "length": [700.0],
                "lts": [2],
            }
        )
        updated = BikePathAnalysis.slope_penalty(edges)
        self.assertEqual(int(updated.iloc[0]["lts"]), 4)


if __name__ == "__main__":
    unittest.main()
