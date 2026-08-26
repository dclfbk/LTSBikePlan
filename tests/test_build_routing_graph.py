import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import LineString

    from ltsbikeplan.domain.crs import WORKING_CRS
    from build_routing_graph import build_routing_graph

    GEO_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - geo deps optional in this env
    GEO_DEPS_AVAILABLE = False


def _edges_gdf():
    # A 3-edge path 10-20-30-40 (node 20 and 30 each shared by two edges -
    # the dedup case), plus one edge with NaN lts (30-40, kept - "soft
    # preference" means an unclassified edge stays routable). Geometry is
    # present but irrelevant to build_routing_graph (only length/lts/
    # istat_code/highway/rule/name are read from this frame - see that
    # module's docstring on why node positions come from a separate nodes
    # frame instead).
    #
    # highway/rule/name cover: a plain street (edge0), a highway=cycleway
    # street reusing edge0's own name (the interning-dedup case), a
    # rule=s1 path with NO name (the -1/unnamed case).
    index = pd.MultiIndex.from_tuples([(10, 20, 0), (20, 30, 0), (30, 40, 0), (40, 50, 0)], names=["u", "v", "key"])
    return gpd.GeoDataFrame(
        {
            "length": [50.0, 30.0, 40.0, float("nan")],
            "lts": [1, 2, float("nan"), 3],
            "istat_code": ["022205"] * 4,
            "highway": ["residential", "cycleway", "track", "residential"],
            "rule": [None, None, None, None],
            "name": ["Via Roma", "Via Roma", float("nan"), "Via Garibaldi"],
            "geometry": [
                LineString([(4300000, 2300000), (4300100, 2300000)]),
                LineString([(4300100, 2300000), (4300200, 2300000)]),
                LineString([(4300200, 2300000), (4300300, 2300000)]),
                LineString([(4300300, 2300000), (4300400, 2300000)]),
            ],
        },
        index=index,
        crs=WORKING_CRS,
    )


def _nodes_df():
    # Real positions for nodes 10/20/30/40, deliberately NOT node 50 - the
    # "no known position for this endpoint" case (e.g. a node dropped by
    # some upstream inconsistency), which must drop the edge that needs it
    # rather than guessing a coordinate for it.
    return pd.DataFrame(
        {
            "osmid": [10, 20, 30, 40],
            "x": [7.700000, 7.700100, 7.700200, 7.700300],
            "y": [45.300000, 45.300010, 45.300020, 45.300030],
        }
    )


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/shapely (geo extras) not installed")
class TestBuildRoutingGraph(unittest.TestCase):
    def test_schema_keys(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(
            set(result.keys()), {"istat", "slug", "generated_at", "nodes", "node_osm_ids", "names", "edges"}
        )

    def test_edge_tuple_has_six_elements(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        for edge in result["edges"]:
            self.assertEqual(len(edge), 6)

    def test_facility_code_per_highway_type(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        # edge0 (10,20,0): highway=residential -> street (0)
        # edge1 (20,30,0): highway=cycleway -> cycleway (1)
        # edge2 (30,40,0): highway=track -> path (2)
        self.assertEqual(result["edges"][0][4], 0)
        self.assertEqual(result["edges"][1][4], 1)
        self.assertEqual(result["edges"][2][4], 2)

    def test_duplicate_name_interned_to_one_entry(self):
        # edge0 and edge1 both carry "Via Roma" - must share one names[]
        # entry, not two, and both edges' name_idx must point at it.
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(result["names"].count("Via Roma"), 1)
        self.assertEqual(result["edges"][0][5], result["edges"][1][5])
        self.assertEqual(result["names"][result["edges"][0][5]], "Via Roma")

    def test_nan_name_gets_sentinel_index(self):
        # edge2 (30,40,0) has no name - name_idx must be -1, not a bogus
        # index into names[].
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(result["edges"][2][5], -1)

    def test_istat_and_slug(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(result["istat"], "022205")
        self.assertEqual(result["slug"], "testcomune")

    def test_shared_endpoint_deduped_to_one_node(self):
        # Node 20 is the `v` of edge (10,20,0) and the `u` of edge
        # (20,30,0) - it must appear exactly once in nodes/node_osm_ids,
        # not twice, and both edges must reference the same local index.
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(result["node_osm_ids"], [10, 20, 30, 40])
        self.assertEqual(len(result["nodes"]), 4)
        first_edge_v_idx = result["edges"][0][1]
        second_edge_u_idx = result["edges"][1][0]
        self.assertEqual(first_edge_v_idx, second_edge_u_idx)

    def test_edge_with_unpositioned_endpoint_dropped(self):
        # Edge (40,50,0) has valid length/lts, but node 50 has no entry in
        # nodes_df - it must be dropped rather than guessing a position,
        # and node 50 must never appear in the output at all.
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(len(result["edges"]), 3)
        self.assertNotIn(50, result["node_osm_ids"])

    def test_nan_length_edge_dropped(self):
        # Edge (40,50,0) also has NaN length (belt-and-suspenders with the
        # missing-node case above) - either reason alone must drop it.
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        lengths = [edge[3] for edge in result["edges"]]
        self.assertNotIn(None, lengths)

    def test_nan_lts_coerced_to_4(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        # Edge (30,40,0), the third valid edge, had lts=NaN in the fixture.
        self.assertEqual(result["edges"][2][2], 4)

    def test_edge_length_rounded_to_one_decimal(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(result["edges"][0][3], 50.0)

    def test_node_coordinates_match_nodes_df_exactly(self):
        # Coordinates come straight from nodes_df (rounded to 6 decimals),
        # not derived/inferred from edge geometry - this is the whole
        # point of the fix (see the module docstring).
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        idx = result["node_osm_ids"].index(20)
        self.assertEqual(result["nodes"][idx], [7.7001, 45.30001])

    def test_node_coordinates_are_finite_lon_lat_pairs(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        for lon, lat in result["nodes"]:
            self.assertTrue(math.isfinite(lon))
            self.assertTrue(math.isfinite(lat))
            self.assertTrue(-180.0 <= lon <= 180.0)
            self.assertTrue(-90.0 <= lat <= 90.0)


if __name__ == "__main__":
    unittest.main()
