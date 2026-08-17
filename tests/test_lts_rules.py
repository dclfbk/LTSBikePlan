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

    def test_surface_penalty_severe_adds_one_regardless_of_length(self):
        # Flat +1 for severe surfaces, any length - losing traction on
        # sand/mud/ground is immediate, but capped at the same +1 a short
        # stretch gets (still a car-free separated path, just a physically
        # harder one - not worth slope_penalty's full +2). Real case:
        # Pachino's beach-access path (OSM way 1160130131), chopped by
        # intersection nodes into ~15-28m graph edges.
        short_edges = pd.DataFrame({"surface": ["ground"], "length": [10.0], "lts": [1]})
        long_edges = pd.DataFrame({"surface": ["ground"], "length": [700.0], "lts": [1]})
        updated_short = BikePathAnalysis.surface_penalty(short_edges)
        updated_long = BikePathAnalysis.surface_penalty(long_edges)
        self.assertEqual(int(updated_short.iloc[0]["lts"]), 2)
        self.assertEqual(int(updated_long.iloc[0]["lts"]), 2)

    def test_surface_penalty_moderate_short_segment_adds_nothing(self):
        edges = pd.DataFrame({"surface": ["gravel"], "length": [50.0], "lts": [1]})
        updated = BikePathAnalysis.surface_penalty(edges)
        self.assertEqual(int(updated.iloc[0]["lts"]), 1)

    def test_surface_penalty_moderate_long_segment_adds_one(self):
        edges = pd.DataFrame({"surface": ["gravel"], "length": [700.0], "lts": [1]})
        updated = BikePathAnalysis.surface_penalty(edges)
        self.assertEqual(int(updated.iloc[0]["lts"]), 2)

    def test_surface_penalty_leaves_paved_untouched(self):
        edges = pd.DataFrame({"surface": ["asphalt"], "length": [700.0], "lts": [1]})
        updated = BikePathAnalysis.surface_penalty(edges)
        self.assertEqual(int(updated.iloc[0]["lts"]), 1)

    def test_surface_penalty_does_not_revive_excluded_edge(self):
        # lts=0 ("not applicable" - e.g. an s9 mountain trail too hard to
        # ride at all) must stay 0 regardless of surface, not get bumped
        # back into the rideable 1-4 scale.
        edges = pd.DataFrame({"surface": ["ground"], "length": [700.0], "lts": [0]})
        updated = BikePathAnalysis.surface_penalty(edges)
        self.assertEqual(int(updated.iloc[0]["lts"]), 0)

    def test_surface_penalty_caps_at_four(self):
        edges = pd.DataFrame({"surface": ["mud"], "length": [700.0], "lts": [4]})
        updated = BikePathAnalysis.surface_penalty(edges)
        self.assertEqual(int(updated.iloc[0]["lts"]), 4)
        # Already at 4 - the reported delta must reflect what actually
        # happened (0), not the nominal +1, so the popup message stays
        # accurate.
        self.assertEqual(int(updated.iloc[0]["surface_penalty_delta"]), 0)

    def test_surface_penalty_ignores_missing_surface_tag(self):
        edges = pd.DataFrame({"surface": [None], "length": [700.0], "lts": [1]})
        updated = BikePathAnalysis.surface_penalty(edges)
        self.assertEqual(int(updated.iloc[0]["lts"]), 1)


class TestGetLanes(unittest.TestCase):
    def test_numeric_and_oneway_values(self):
        edges = pd.DataFrame({"lanes": ["3", None], "oneway": [False, True]})
        updated = BikePathAnalysis.get_lanes(edges)
        self.assertEqual(list(updated["lanes_assumed"]), [3, 1])  # oneway forces 1 regardless of default_lanes

    def test_malformed_lanes_value_falls_back_to_default_instead_of_crashing(self):
        # A single malformed way in Polistena had lanes="\\" (a literal
        # backslash) - crashed `np.array(x, dtype="int")` with
        # `ValueError: invalid literal for int() with base 10: '\\'`,
        # taking down the whole area's compute-lts run over one bad tag.
        edges = pd.DataFrame({"lanes": ["\\"], "oneway": [False]})
        updated = BikePathAnalysis.get_lanes(edges)
        self.assertEqual(updated.iloc[0]["lanes_assumed"], 2)

    def test_multi_value_list_takes_the_max(self):
        edges = pd.DataFrame({"lanes": [["2", "4"]], "oneway": [False]})
        updated = BikePathAnalysis.get_lanes(edges)
        self.assertEqual(updated.iloc[0]["lanes_assumed"], 4)


class TestGetMaxSpeed(unittest.TestCase):
    def test_numeric_and_missing_values(self):
        edges = pd.DataFrame({"maxspeed": ["30", None], "highway": ["residential", "residential"]})
        updated = BikePathAnalysis.get_max_speed(edges)
        self.assertEqual(list(updated["maxspeed_assumed"]), [30, 50])  # 50 = local default for a missing tag

    def test_italian_implicit_speed_zones(self):
        # OSM's Italy-specific implicit-speed convention: maxspeed can be a
        # zone name instead of a number. IT:rural was the one missing here -
        # confirmed live on Paceco (54 real highway=tertiary edges tagged
        # maxspeed=IT:rural) - it fell through to `return val`, leaving the
        # literal string "IT:rural" in maxspeed_assumed and crashing the
        # next `<=` comparison against it downstream in mixed_traffic()
        # with `TypeError: '<=' not supported between instances of 'str'
        # and 'int'`.
        edges = pd.DataFrame(
            {
                "maxspeed": ["IT:urban", "IT:rural", "IT:motorway"],
                "highway": ["residential", "tertiary", "motorway"],
            }
        )
        updated = BikePathAnalysis.get_max_speed(edges)
        self.assertEqual(list(updated["maxspeed_assumed"]), [50, 90, 130])
        self.assertTrue(pd.api.types.is_numeric_dtype(updated["maxspeed_assumed"]))

    def test_unrecognized_string_falls_back_to_local_instead_of_leaking_the_string(self):
        edges = pd.DataFrame({"maxspeed": ["walk"], "highway": ["residential"]})
        updated = BikePathAnalysis.get_max_speed(edges)
        self.assertEqual(updated.iloc[0]["maxspeed_assumed"], 50)


if __name__ == "__main__":
    unittest.main()
