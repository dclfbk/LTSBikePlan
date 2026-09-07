import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import LineString, Point, Polygon

    from ltsbikeplan.domain.network_pruning import drop_isolated_bikeable_components

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/networkx/shapely (geo extras) not installed")
class TestDropIsolatedBikeableComponents(unittest.TestCase):
    def setUp(self):
        # A roughly 1km x 1km comune boundary around Trento's real
        # coordinates - small enough that a "near the edge" node and a
        # "deep interior" node are unambiguously different distances from
        # it once reprojected to a metric CRS.
        self.boundary = Polygon([(11.10, 46.05), (11.12, 46.05), (11.12, 46.07), (11.10, 46.07)])

        # Main bikeable network: a long (>1km) line comfortably inside the
        # boundary - never a candidate for dropping regardless of length
        # threshold.
        main_nodes = {
            1: Point(11.108, 46.055),
            2: Point(11.110, 46.060),
            3: Point(11.112, 46.065),
        }
        # Short bikeable island deep in the interior, far from the
        # boundary - stands in for a park path / Venice sottoportego knot
        # only reachable from the main network via non-bikeable links.
        interior_nodes = {
            10: Point(11.109, 46.058),
            11: Point(11.1092, 46.0582),
        }
        # A node bridging the interior island to the main network, but
        # ONLY via a non-bikeable (lts=0, e.g. unramped steps) edge - the
        # island must still count as isolated for THIS feature's purposes,
        # since a cyclist can't actually use that link.
        excluded_link_node = {12: Point(11.1094, 46.0584)}

        # Short bikeable island of the same size/shape, but sitting right
        # on the boundary line - stands in for a road genuinely cut short
        # by the comune extract's own edge.
        boundary_nodes = {
            20: Point(11.10005, 46.058),
            21: Point(11.10005, 46.0582),
        }

        all_nodes = {**main_nodes, **interior_nodes, **excluded_link_node, **boundary_nodes}
        self.gdf_nodes = gpd.GeoDataFrame(
            {"geometry": list(all_nodes.values())}, index=list(all_nodes.keys()), crs="EPSG:4326"
        )

        def edge_row(u, v, length_m, lts):
            return {"geometry": LineString([all_nodes[u], all_nodes[v]]), "length": length_m, "lts": lts}

        edges = {
            (1, 2, 0): edge_row(1, 2, 600.0, 1),
            (2, 3, 0): edge_row(2, 3, 600.0, 1),  # main bikeable component: 1200m, well above the threshold
            (10, 11, 0): edge_row(10, 11, 30.0, 1),  # interior bikeable island: 30m, far from boundary
            (11, 12, 0): edge_row(11, 12, 5.0, 0),  # non-bikeable link (e.g. unramped steps) to the main network
            (12, 3, 0): edge_row(12, 3, 5.0, 0),  # (also non-bikeable) - so the FULL graph is one component
            (20, 21, 0): edge_row(20, 21, 30.0, 1),  # boundary-touching bikeable island: 30m, right at the boundary
        }
        index = pd.MultiIndex.from_tuples(list(edges.keys()), names=["u", "v", "key"])
        self.all_lts = pd.DataFrame(
            {
                "length": [e["length"] for e in edges.values()],
                "lts": [e["lts"] for e in edges.values()],
            },
            index=index,
        )

    def test_drops_short_bikeable_island_reachable_only_via_excluded_link(self):
        # The whole FULL physical graph (including the lts=0 link) is one
        # single connected piece - the fix under test must still treat the
        # interior bikeable island as isolated, since a cyclist can't ride
        # the lts=0 link connecting it to the main network.
        result = drop_isolated_bikeable_components(self.gdf_nodes, self.all_lts, self.boundary)
        self.assertNotIn((10, 11, 0), result.index)

    def test_keeps_short_bikeable_island_touching_the_boundary(self):
        result = drop_isolated_bikeable_components(self.gdf_nodes, self.all_lts, self.boundary)
        self.assertIn((20, 21, 0), result.index)

    def test_keeps_the_main_bikeable_network_untouched(self):
        result = drop_isolated_bikeable_components(self.gdf_nodes, self.all_lts, self.boundary)
        self.assertIn((1, 2, 0), result.index)
        self.assertIn((2, 3, 0), result.index)

    def test_leaves_non_bikeable_edges_alone(self):
        # lts=0 edges are never candidates for dropping by this function,
        # even ones dangling off a dropped island - they're already hidden
        # from the map by default.
        result = drop_isolated_bikeable_components(self.gdf_nodes, self.all_lts, self.boundary)
        self.assertIn((11, 12, 0), result.index)
        self.assertIn((12, 3, 0), result.index)

    def test_no_boundary_polygon_is_a_no_op(self):
        result = drop_isolated_bikeable_components(self.gdf_nodes, self.all_lts, None)
        self.assertEqual(len(result), len(self.all_lts))

    def test_single_bikeable_component_is_a_no_op(self):
        only_main = self.all_lts.loc[[(1, 2, 0), (2, 3, 0)]]
        result = drop_isolated_bikeable_components(self.gdf_nodes, only_main, self.boundary)
        self.assertEqual(len(result), 2)

    def test_empty_all_lts_is_a_no_op(self):
        empty = self.all_lts.iloc[0:0]
        result = drop_isolated_bikeable_components(self.gdf_nodes, empty, self.boundary)
        self.assertEqual(len(result), 0)

    def test_no_bikeable_edges_at_all_is_a_no_op(self):
        all_excluded = self.all_lts.copy()
        all_excluded["lts"] = 0
        result = drop_isolated_bikeable_components(self.gdf_nodes, all_excluded, self.boundary)
        self.assertEqual(len(result), len(all_excluded))


if __name__ == "__main__":
    unittest.main()
