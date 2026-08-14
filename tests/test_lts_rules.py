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

    def test_steps_without_ramp_are_not_bikeable(self):
        edges = pd.DataFrame(
            {
                "highway": ["steps", "residential"],
            }
        )

        steps_edges, other_edges = BikePathAnalysis.steps_analysis(edges)
        self.assertEqual(len(steps_edges), 1)
        self.assertEqual(len(other_edges), 1)
        self.assertEqual(steps_edges.iloc[0]["rule"], "p8")
        self.assertEqual(steps_edges.iloc[0]["lts"], 0)

    def test_steps_with_bicycle_ramp_are_lts_1(self):
        edges = pd.DataFrame(
            {
                "highway": ["steps", "steps", "steps"],
                "ramp": ["yes", "no", "no"],
                "ramp:bicycle": ["no", "yes", "no"],
            }
        )

        steps_edges, other_edges = BikePathAnalysis.steps_analysis(edges)
        self.assertEqual(len(steps_edges), 3)
        self.assertEqual(len(other_edges), 0)
        self.assertListEqual(list(steps_edges["rule"]), ["p9", "p9", "p8"])
        self.assertListEqual(list(steps_edges["lts"]), [1, 1, 0])

    def test_steps_analysis_without_ramp_columns(self):
        edges = pd.DataFrame({"highway": ["steps"]})

        steps_edges, other_edges = BikePathAnalysis.steps_analysis(edges)
        self.assertEqual(steps_edges.iloc[0]["rule"], "p8")
        self.assertEqual(steps_edges.iloc[0]["lts"], 0)
        self.assertTrue(other_edges.empty)

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
