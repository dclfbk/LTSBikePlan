import json
import math
import struct
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
    from build_routing_graph import UNKNOWN_SLOPE_CLASS_CODE, build_routing_graph, encode_routing_graph_binary

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
    # rule=s1 path with NO name (the -1/unnamed case). edge4 (40,60,0) is
    # LTS 0 ("Non ciclabile") with a real length AND a real position for
    # node 60 (nodes_df below) - isolates "dropped because LTS 0" from the
    # already-covered "dropped because no known position"/"dropped because
    # NaN length" cases (edge3, (40,50,0)).
    index = pd.MultiIndex.from_tuples(
        [(10, 20, 0), (20, 30, 0), (30, 40, 0), (40, 50, 0), (40, 60, 0)], names=["u", "v", "key"]
    )
    return gpd.GeoDataFrame(
        {
            "length": [50.0, 30.0, 40.0, float("nan"), 25.0],
            "lts": [1, 2, float("nan"), 3, 0],
            "istat_code": ["022205"] * 5,
            "highway": ["residential", "cycleway", "track", "residential", "motorway"],
            "rule": [None, None, None, None, None],
            "name": ["Via Roma", "Via Roma", float("nan"), "Via Garibaldi", "Autostrada Test"],
            # edge0 flat, edge1 steep (the two that survive with a real
            # slope_class - covers both a recognized code and the "0" code
            # not being confused with "unknown"), edge2 NaN (the "no
            # reliable slope reading" case - must NOT be coerced to flat).
            # edge3/edge4 are dropped anyway (NaN length / LTS 0), values
            # here are irrelevant.
            "slope_class": ["0-3: flat", "8-10: hard", float("nan"), "5-8: medium", "10-20: extreme"],
            "geometry": [
                LineString([(4300000, 2300000), (4300100, 2300000)]),
                LineString([(4300100, 2300000), (4300200, 2300000)]),
                LineString([(4300200, 2300000), (4300300, 2300000)]),
                LineString([(4300300, 2300000), (4300400, 2300000)]),
                LineString([(4300300, 2300000), (4300500, 2300000)]),
            ],
        },
        index=index,
        crs=WORKING_CRS,
    )


def _nodes_df():
    # Real positions for nodes 10/20/30/40/60, deliberately NOT node 50 -
    # the "no known position for this endpoint" case (e.g. a node dropped
    # by some upstream inconsistency), which must drop the edge that needs
    # it rather than guessing a coordinate for it. Node 60 DOES have a
    # position - it's only ever reached via the LTS-0 edge (40,60,0), so
    # if it's missing from the output that's proof the edge was dropped
    # for being LTS 0, not for a missing position.
    return pd.DataFrame(
        {
            "osmid": [10, 20, 30, 40, 60],
            "x": [7.700000, 7.700100, 7.700200, 7.700300, 7.700500],
            "y": [45.300000, 45.300010, 45.300020, 45.300030, 45.300050],
        }
    )


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/shapely (geo extras) not installed")
class TestBuildRoutingGraph(unittest.TestCase):
    def test_schema_keys(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(
            set(result.keys()), {"istat", "slug", "generated_at", "nodes", "node_osm_ids", "names", "edges"}
        )

    def test_edge_tuple_has_seven_elements(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        for edge in result["edges"]:
            self.assertEqual(len(edge), 7)

    def test_slope_class_coded_per_edge(self):
        # edge0 (10,20,0): "0-3: flat" -> code 0
        # edge1 (20,30,0): "8-10: hard" -> code 3
        # edge2 (30,40,0): NaN -> UNKNOWN_SLOPE_CLASS_CODE, NOT code 0 -
        # missing data must not be silently treated as "flat".
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(result["edges"][0][6], 0)
        self.assertEqual(result["edges"][1][6], 3)
        self.assertEqual(result["edges"][2][6], UNKNOWN_SLOPE_CLASS_CODE)

    def test_missing_slope_class_column_defaults_to_unknown(self):
        # An older/partial `_all_lts.parquet` without a slope_class column
        # at all must not crash - every edge falls back to "unknown", same
        # as an explicit NaN.
        edges_gdf = _edges_gdf().drop(columns=["slope_class"])
        result = build_routing_graph(edges_gdf, _nodes_df(), "testcomune")
        for edge in result["edges"]:
            self.assertEqual(edge[6], UNKNOWN_SLOPE_CLASS_CODE)

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
        # and node 50 must never appear in the output at all. (edge4,
        # (40,60,0), is also dropped, but for the separate LTS-0 reason
        # covered by test_lts_zero_edge_excluded_not_just_penalized below
        # - the count here stays 3 either way.)
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertEqual(len(result["edges"]), 3)
        self.assertNotIn(50, result["node_osm_ids"])

    def test_lts_zero_edge_excluded_not_just_penalized(self):
        # LTS 0 ("Non ciclabile") means no bike access at all, not just
        # "very stressful" - edge (40,60,0) must be dropped entirely
        # (never appear with lts=0 in the output), not merely kept with a
        # high cost. Node 60 has a real position in nodes_df and is
        # reached ONLY via this edge, so its absence from node_osm_ids is
        # proof the edge itself was excluded, not that its endpoint
        # happened to lack a position (that's the separate case above).
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        self.assertNotIn(60, result["node_osm_ids"])
        self.assertTrue(all(edge[2] != 0 for edge in result["edges"]))

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


def _decode_binary_pure_python(blob: bytes) -> dict:
    """A from-scratch, independent decoder (deliberately NOT importing
    anything from encode_routing_graph_binary) mirroring
    web/routing.js's decodeRoutingGraphBinary byte-for-byte - the point is
    to catch a Python-side layout bug that a decoder sharing the same
    (possibly also wrong) assumptions couldn't. The real cross-language
    check (this Python encoder's output actually decoded BY the real JS
    function) is a separate Node-based test, not part of this suite."""
    (header_len,) = struct.unpack_from("<I", blob, 0)
    header = json.loads(blob[4 : 4 + header_len].decode("utf-8"))
    nc, ec = header["nodeCount"], header["edgeCount"]

    offset = 4 + header_len
    offset += (8 - (offset % 8)) % 8

    def read(dtype_fmt, count, size):
        nonlocal offset
        values = struct.unpack_from(f"<{count}{dtype_fmt}", blob, offset)
        offset += count * size
        return values

    node_lons = read("f", nc, 4)
    node_lats = read("f", nc, 4)
    node_osm_ids = read("d", nc, 8)
    edge_u = read("I", ec, 4)
    edge_v = read("I", ec, 4)
    edge_length = read("f", ec, 4)
    edge_name_idx = read("i", ec, 4)
    edge_lts = read("B", ec, 1)
    edge_facility = read("B", ec, 1)
    edge_slope_class = read("B", ec, 1)

    return {
        "slug": header["slug"],
        "names": header["names"],
        "nodes": list(zip(node_lons, node_lats)),
        "node_osm_ids": list(node_osm_ids),
        "edges": list(zip(edge_u, edge_v, edge_lts, edge_length, edge_facility, edge_name_idx, edge_slope_class)),
    }


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/shapely (geo extras) not installed")
class TestEncodeRoutingGraphBinary(unittest.TestCase):
    def test_round_trip_matches_the_source_dict(self):
        result = build_routing_graph(_edges_gdf(), _nodes_df(), "testcomune")
        decoded = _decode_binary_pure_python(encode_routing_graph_binary(result))

        self.assertEqual(decoded["slug"], result["slug"])
        self.assertEqual(decoded["names"], result["names"])
        self.assertEqual(decoded["node_osm_ids"], result["node_osm_ids"])
        self.assertEqual(len(decoded["edges"]), len(result["edges"]))

        # float32 round-trip isn't bit-exact vs the source float64s - assert
        # "close enough for a coordinate/length", not equality.
        for (dec_lon, dec_lat), (src_lon, src_lat) in zip(decoded["nodes"], result["nodes"]):
            self.assertAlmostEqual(dec_lon, src_lon, places=5)
            self.assertAlmostEqual(dec_lat, src_lat, places=5)
        for dec_edge, src_edge in zip(decoded["edges"], result["edges"]):
            dec_u, dec_v, dec_lts, dec_len, dec_fac, dec_name_idx, dec_slope = dec_edge
            src_u, src_v, src_lts, src_len, src_fac, src_name_idx, src_slope = src_edge
            self.assertEqual(
                (dec_u, dec_v, dec_lts, dec_fac, dec_name_idx, dec_slope),
                (src_u, src_v, src_lts, src_fac, src_name_idx, src_slope),
            )
            self.assertAlmostEqual(dec_len, src_len, places=1)

    def test_empty_graph_encodes_and_decodes_without_error(self):
        # nodeCount=0/edgeCount=0 - the padding-and-section-length math
        # (all `count * elementSize`) must not divide-by-zero or misindex
        # on an empty comune's routing graph (a real, if rare, case).
        empty = {"slug": "empty", "names": [], "nodes": [], "node_osm_ids": [], "edges": []}
        decoded = _decode_binary_pure_python(encode_routing_graph_binary(empty))
        self.assertEqual(decoded["nodes"], [])
        self.assertEqual(decoded["edges"], [])
        self.assertEqual(decoded["slug"], "empty")


if __name__ == "__main__":
    unittest.main()
