import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import pandas as pd

    from ltsbikeplan.domain.network_centrality import annotate_dead_end_branches, annotate_edge_centrality, _bucket_centrality

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "networkx/pandas (geo extras) not installed")
class TestAnnotateEdgeCentrality(unittest.TestCase):
    def test_bridge_edge_has_higher_centrality_than_a_dead_end(self):
        # Two triangles (dense clusters) joined by a single bridge edge,
        # plus a dead-end leaf hanging off cluster A. Every shortest path
        # between the two clusters must cross the bridge; almost none cross
        # the leaf.
        edges = [
            (1, 2, 0, 1.0), (2, 3, 0, 1.0), (1, 3, 0, 1.0),  # cluster A
            (4, 5, 0, 1.0), (5, 6, 0, 1.0), (4, 6, 0, 1.0),  # cluster B
            (3, 4, 0, 1.0),  # bridge
            (1, 7, 0, 1.0),  # dead-end leaf
        ]
        index = pd.MultiIndex.from_tuples([(u, v, k) for u, v, k, _ in edges], names=["u", "v", "key"])
        all_lts = pd.DataFrame({"length": [length for *_, length in edges]}, index=index)

        result = annotate_edge_centrality(all_lts)

        bridge_centrality = result.loc[(3, 4, 0), "centrality"]
        leaf_centrality = result.loc[(1, 7, 0), "centrality"]
        self.assertGreater(bridge_centrality, leaf_centrality)
        self.assertIn(result.loc[(3, 4, 0), "centrality_class"], {"low", "medium", "high", "very_high", "zero"})


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "networkx/pandas (geo extras) not installed")
class TestAnnotateDeadEndBranches(unittest.TestCase):
    def test_non_bridge_edges_get_nan(self):
        # Same two-triangles-plus-bridge-plus-leaf fixture as the
        # centrality test above - triangle edges have an alternate route
        # (the other two sides), so removing any one of them alone can't
        # disconnect anything.
        edges = [
            (1, 2, 0, 1.0), (2, 3, 0, 1.0), (1, 3, 0, 1.0),
            (4, 5, 0, 1.0), (5, 6, 0, 1.0), (4, 6, 0, 1.0),
            (3, 4, 0, 1.0),
            (1, 7, 0, 1.0),
        ]
        index = pd.MultiIndex.from_tuples([(u, v, k) for u, v, k, _ in edges], names=["u", "v", "key"])
        all_lts = pd.DataFrame({"length": [length for *_, length in edges]}, index=index)

        result = annotate_dead_end_branches(all_lts)
        for triangle_edge in [(1, 2, 0), (2, 3, 0), (1, 3, 0), (4, 5, 0), (5, 6, 0), (4, 6, 0)]:
            self.assertTrue(pd.isna(result.loc[triangle_edge, "served_branch_km"]))

    def test_leaf_bridge_serves_zero_further_km(self):
        edges = [
            (1, 2, 0, 1.0), (2, 3, 0, 1.0), (1, 3, 0, 1.0),
            (4, 5, 0, 1.0), (5, 6, 0, 1.0), (4, 6, 0, 1.0),
            (3, 4, 0, 1.0),
            (1, 7, 0, 1.0),
        ]
        index = pd.MultiIndex.from_tuples([(u, v, k) for u, v, k, _ in edges], names=["u", "v", "key"])
        all_lts = pd.DataFrame({"length": [length for *_, length in edges]}, index=index)

        result = annotate_dead_end_branches(all_lts)
        self.assertEqual(result.loc[(1, 7, 0), "served_branch_km"], 0.0)

    def test_bridge_between_two_clusters_reports_smaller_cluster_km(self):
        # A long dead-end chain (0-1-2-3-4, 100m per segment) hangs off a
        # main network big enough to dwarf it - the chain is unambiguously
        # the smaller side for every edge along it, and the edge closest to
        # the main network should report the largest served_branch_km
        # (the whole chain), shrinking as you move deeper into the
        # dead-end.
        edges = [
            (100, 101, 0, 500.0), (101, 102, 0, 500.0), (100, 102, 0, 500.0),
            (0, 1, 0, 100.0), (1, 2, 0, 100.0), (2, 3, 0, 100.0), (3, 4, 0, 100.0),
            (100, 0, 0, 50.0),
        ]
        index = pd.MultiIndex.from_tuples([(u, v, k) for u, v, k, _ in edges], names=["u", "v", "key"])
        all_lts = pd.DataFrame({"length": [length for *_, length in edges]}, index=index)

        result = annotate_dead_end_branches(all_lts)
        km_0_1 = result.loc[(0, 1, 0), "served_branch_km"]
        km_1_2 = result.loc[(1, 2, 0), "served_branch_km"]
        km_2_3 = result.loc[(2, 3, 0), "served_branch_km"]
        km_3_4 = result.loc[(3, 4, 0), "served_branch_km"]
        self.assertAlmostEqual(km_0_1, 0.3)  # 100+100+100m beyond this edge
        self.assertAlmostEqual(km_1_2, 0.2)
        self.assertAlmostEqual(km_2_3, 0.1)
        self.assertAlmostEqual(km_3_4, 0.0)
        self.assertGreater(km_0_1, km_1_2)
        self.assertGreater(km_1_2, km_2_3)
        self.assertGreater(km_2_3, km_3_4)


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "networkx/pandas (geo extras) not installed")
class TestBucketCentrality(unittest.TestCase):
    def test_all_zero_series_returns_zero_bucket_without_raising(self):
        values = pd.Series([0.0, 0.0, 0.0])
        result = _bucket_centrality(values)
        self.assertTrue((result == "zero").all())

    def test_mixed_zero_and_tied_values_buckets_without_raising(self):
        # A real street network's betweenness is often zero-heavy on
        # residential dead-ends - this is the case a plain pd.qcut(..., 4)
        # can raise on (duplicate bin edges) if not handled defensively.
        values = pd.Series([0.0] * 5 + [1, 1, 2, 2, 3, 3, 4, 4, 5, 5])
        result = _bucket_centrality(values)
        self.assertTrue((result.iloc[:5] == "zero").all())
        self.assertTrue(result.iloc[5:].isin(["low", "medium", "high", "very_high"]).all())


if __name__ == "__main__":
    unittest.main()
