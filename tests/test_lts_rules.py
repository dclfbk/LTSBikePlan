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

    def test_biking_permitted_marks_trunk_motorroad_not_allowed(self):
        edges = pd.DataFrame(
            {
                "bicycle": ["yes", "yes", "yes"],
                "access": ["yes", "yes", "yes"],
                "highway": ["trunk", "trunk_link", "trunk"],
                "motorroad": ["yes", "yes", "no"],
            }
        )

        allowed, not_allowed = BikePathAnalysis.biking_permitted(edges)
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(not_allowed), 2)
        self.assertTrue((not_allowed["rule"] == "p10").all())

    def test_biking_permitted_without_motorroad_column(self):
        # Plenty of extracts never carry the tag at all - shouldn't KeyError,
        # and a bare trunk with no motorroad info stays allowed (the legal
        # restriction isn't automatic from the highway class alone).
        edges = pd.DataFrame(
            {
                "bicycle": ["yes"],
                "access": ["yes"],
                "highway": ["trunk"],
            }
        )

        allowed, not_allowed = BikePathAnalysis.biking_permitted(edges)
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(not_allowed), 0)

    def test_hard_sac_scale_path_is_reclassified_as_impassable(self):
        edges = pd.DataFrame(
            {
                "highway": ["path", "path", "path"],
                "sac_scale": ["hiking", "mountain_hiking", "difficult_alpine_hiking"],
            }
        )

        separated, not_separated = BikePathAnalysis.is_separated_path(edges)
        self.assertTrue(not_separated.empty)
        self.assertListEqual(list(separated["rule"]), ["s1", "s9", "s9"])

    def test_hard_mtb_scale_footway_is_reclassified_as_impassable(self):
        edges = pd.DataFrame(
            {
                "highway": ["footway", "footway", "footway"],
                "mtb:scale": ["0", "1", "3"],
            }
        )

        separated, _ = BikePathAnalysis.is_separated_path(edges)
        self.assertListEqual(list(separated["rule"]), ["s2", "s2", "s9"])

    def test_sac_scale_does_not_affect_a_dedicated_cycleway(self):
        # sac_scale/mtb:scale describe trail difficulty - a real cycleway
        # (s3) isn't a trail, so the tag (however implausible on one) should
        # never downgrade it.
        edges = pd.DataFrame(
            {
                "highway": ["cycleway"],
                "sac_scale": ["difficult_alpine_hiking"],
            }
        )

        separated, _ = BikePathAnalysis.is_separated_path(edges)
        self.assertEqual(separated.iloc[0]["rule"], "s3")

    def test_is_separated_path_without_sac_scale_or_mtb_scale_columns(self):
        edges = pd.DataFrame({"highway": ["path"]})

        separated, not_separated = BikePathAnalysis.is_separated_path(edges)
        self.assertEqual(separated.iloc[0]["rule"], "s1")
        self.assertTrue(not_separated.empty)

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
