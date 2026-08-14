import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import pandas as pd

    from ltsbikeplan.domain.gap_analysis import annotate_gap_components

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/networkx (geo extras) not installed")
class TestAnnotateGapComponents(unittest.TestCase):
    def setUp(self):
        # Two low-stress islands (1-2-3 and 10-11-12), connected only by a
        # single LTS-4 edge (3-10) - the edge a planner would want to fix to
        # merge them into one island. An isolated LTS-4 edge elsewhere (20-21)
        # touches no island and should not be flagged.
        edges = [
            (1, 2, 0, 1),
            (2, 3, 0, 2),
            (10, 11, 0, 1),
            (11, 12, 0, 2),
            (3, 10, 0, 4),
            (20, 21, 0, 4),
        ]
        index = pd.MultiIndex.from_tuples([(u, v, k) for u, v, k, _ in edges], names=["u", "v", "key"])
        self.all_lts = pd.DataFrame({"lts": [lts for *_, lts in edges]}, index=index)

    def test_low_stress_edges_get_a_component_id(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea")
        comp_a = annotated.loc[(1, 2, 0), "gap_component"]
        comp_b = annotated.loc[(2, 3, 0), "gap_component"]
        self.assertEqual(comp_a, comp_b)
        self.assertTrue(comp_a.startswith("TestArea:"))

    def test_two_islands_get_different_component_ids(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea")
        island_1 = annotated.loc[(1, 2, 0), "gap_component"]
        island_2 = annotated.loc[(10, 11, 0), "gap_component"]
        self.assertNotEqual(island_1, island_2)

    def test_connecting_edge_is_flagged_as_gap_edge(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea")
        connector = annotated.loc[(3, 10, 0)]
        self.assertTrue(connector["is_gap_edge"])
        island_1 = annotated.loc[(1, 2, 0), "gap_component"]
        island_2 = annotated.loc[(10, 11, 0), "gap_component"]
        touched = set(connector["gap_connects"].split(","))
        self.assertEqual(touched, {island_1, island_2})

    def test_isolated_high_stress_edge_is_not_flagged(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea")
        isolated = annotated.loc[(20, 21, 0)]
        self.assertFalse(isolated["is_gap_edge"])
        self.assertTrue(pd.isna(isolated["gap_connects"]))

    def test_low_stress_edges_are_never_gap_edges(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea")
        self.assertFalse(annotated.loc[(1, 2, 0), "is_gap_edge"])


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/networkx (geo extras) not installed")
class TestMinIslandLengthThreshold(unittest.TestCase):
    def setUp(self):
        # Island A (1-2-3): two long edges, 600m total - above a 0.5km
        # threshold. Island B (10-11-12): two short edges, 20m total - a
        # stand-in for a 2-edge residential loop in an isolated hamlet,
        # below threshold. Each touched by its own high-stress connector.
        edges = [
            (1, 2, 0, 1, 300.0), (2, 3, 0, 2, 300.0),
            (10, 11, 0, 1, 10.0), (11, 12, 0, 2, 10.0),
            (3, 100, 0, 4, 50.0),   # touches only island A (large)
            (12, 200, 0, 4, 50.0),  # touches only island B (small)
        ]
        index = pd.MultiIndex.from_tuples([(u, v, k) for u, v, k, *_ in edges], names=["u", "v", "key"])
        self.all_lts = pd.DataFrame(
            {"lts": [lts for _, _, _, lts, _ in edges], "length": [length for *_, length in edges]},
            index=index,
        )

    def test_edge_touching_large_island_stays_flagged(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea", min_island_length_km=0.5)
        self.assertTrue(annotated.loc[(3, 100, 0), "is_gap_edge"])

    def test_edge_touching_only_small_island_is_downgraded(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea", min_island_length_km=0.5)
        row = annotated.loc[(12, 200, 0)]
        self.assertFalse(row["is_gap_edge"])
        self.assertTrue(pd.isna(row["gap_connects"]))

    def test_default_none_keeps_both_flagged(self):
        annotated = annotate_gap_components(self.all_lts, "TestArea")
        self.assertTrue(annotated.loc[(3, 100, 0), "is_gap_edge"])
        self.assertTrue(annotated.loc[(12, 200, 0), "is_gap_edge"])


if __name__ == "__main__":
    unittest.main()
