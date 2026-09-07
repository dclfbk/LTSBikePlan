import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import LineString, Point, Polygon

    from ltsbikeplan.domain.network_pruning import drop_isolated_interior_components

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/networkx/shapely (geo extras) not installed")
class TestDropIsolatedInteriorComponents(unittest.TestCase):
    def setUp(self):
        # A roughly 1km x 1km comune boundary around Trento's real
        # coordinates - small enough that a "near the edge" node and a
        # "deep interior" node are unambiguously different distances from
        # it once reprojected to a metric CRS.
        self.boundary = Polygon([(11.10, 46.05), (11.12, 46.05), (11.12, 46.07), (11.10, 46.07)])

        # Main network: a long (>1km) line comfortably inside the boundary -
        # never a candidate for dropping regardless of length threshold.
        main_nodes = {
            1: Point(11.108, 46.055),
            2: Point(11.110, 46.060),
            3: Point(11.112, 46.065),
        }
        # Small isolated component (a "park path" stand-in): short, deep in
        # the interior, far from the boundary.
        interior_nodes = {
            10: Point(11.109, 46.058),
            11: Point(11.1092, 46.0582),
        }
        # Small component of the same size/shape, but sitting right on the
        # boundary line - stands in for a road genuinely cut short by the
        # comune extract's own edge.
        boundary_nodes = {
            20: Point(11.10005, 46.058),
            21: Point(11.10005, 46.0582),
        }

        all_nodes = {**main_nodes, **interior_nodes, **boundary_nodes}
        self.gdf_nodes = gpd.GeoDataFrame(
            {"geometry": list(all_nodes.values())}, index=list(all_nodes.keys()), crs="EPSG:4326"
        )

        def edge_row(u, v, length_m):
            return {"geometry": LineString([all_nodes[u], all_nodes[v]]), "length": length_m}

        edges = {
            (1, 2, 0): edge_row(1, 2, 600.0),
            (2, 3, 0): edge_row(2, 3, 600.0),  # main component: 1200m total, well above the threshold
            (10, 11, 0): edge_row(10, 11, 30.0),  # interior island: 30m, well below threshold, far from boundary
            (20, 21, 0): edge_row(20, 21, 30.0),  # boundary island: 30m, well below threshold, right at the boundary
        }
        index = pd.MultiIndex.from_tuples(list(edges.keys()), names=["u", "v", "key"])
        self.gdf_edges = gpd.GeoDataFrame(
            {"geometry": [e["geometry"] for e in edges.values()], "length": [e["length"] for e in edges.values()]},
            index=index,
            crs="EPSG:4326",
        )

    def test_drops_short_interior_component_far_from_boundary(self):
        result = drop_isolated_interior_components(self.gdf_nodes, self.gdf_edges, self.boundary)
        self.assertNotIn((10, 11, 0), result.index)

    def test_keeps_short_component_touching_the_boundary(self):
        result = drop_isolated_interior_components(self.gdf_nodes, self.gdf_edges, self.boundary)
        self.assertIn((20, 21, 0), result.index)

    def test_keeps_the_main_network_untouched(self):
        result = drop_isolated_interior_components(self.gdf_nodes, self.gdf_edges, self.boundary)
        self.assertIn((1, 2, 0), result.index)
        self.assertIn((2, 3, 0), result.index)

    def test_no_boundary_polygon_is_a_no_op(self):
        result = drop_isolated_interior_components(self.gdf_nodes, self.gdf_edges, None)
        self.assertEqual(len(result), len(self.gdf_edges))

    def test_single_component_network_is_a_no_op(self):
        # No small/interior components at all - just the main line.
        edges_only_main = self.gdf_edges.loc[[(1, 2, 0), (2, 3, 0)]]
        result = drop_isolated_interior_components(self.gdf_nodes, edges_only_main, self.boundary)
        self.assertEqual(len(result), 2)

    def test_empty_edges_is_a_no_op(self):
        empty = self.gdf_edges.iloc[0:0]
        result = drop_isolated_interior_components(self.gdf_nodes, empty, self.boundary)
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
