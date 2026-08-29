#!/usr/bin/env python3
"""Exports one comune's client-side routable graph, for web/routing.js's
in-browser A* (see web/app.js's RoutingControl). Companion to
scripts/build_tiles.sh's cartographic PMTiles export - same
`<slug> [data_dir]` invocation shape, reads two of compute_lts.py's
outputs: `<slug>_all_lts.parquet` (edges: length/lts, always kept - unlike
its .geojson twin, see build_italy_map_comuni_cron.sh's process_comune)
and `<slug>_nodes.parquet` (real node positions: osmid/x/y).

Node identity is the edge's real, un-renumbered OSM node id (osmnx/pyrosm
never remaps it - no truncate_graph_polygon/simplify_graph/
consolidate_intersections call exists anywhere in this project's ingestion
path, see services/osm_pbf_service.py). Two independently-fetched adjacent
comuni therefore share the same id for any OSM node that lies in both
extracts - the cross-file join key web/routing.js's mergeRoutingGraphs()
uses to stitch a route across a comune boundary, with no coordinate-
rounding/tolerance guesswork needed. Verified on a real adjacent-comune
pair (Aglie/Bairo, Aug 2026): shared OSM node ids matched to the exact
same coordinate in both files.

Node COORDINATES come from `<slug>_nodes.parquet` - real positions, not
inferred from edge geometry endpoints. An earlier version of this script
took a shortcut (an edge's LineString's first/last coordinate = u's/v's
own position) that turned out to be wrong: this project's edge geometry is
not guaranteed oriented u->v for every row - a two-way street's reverse-
direction (v,u) row can carry the SAME unflipped geometry as its (u,v)
counterpart (confirmed on real data: both direction-rows of the same
physical way segment had identical geom.coords[0]/[-1]). That shortcut
measured up to ~190m of node misplacement on a real case. Don't
reintroduce it.

Usage: scripts/build_routing_graph.py <area_slug> [data_dir]
"""
from __future__ import annotations

import json
import os
import struct
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

import geopandas as gpd
import numpy as np
import pandas as pd

# LTS coerced to this when NaN (unclassified edge) - stays usable as a
# last-resort route rather than vanishing from the graph, matching
# domain/routing_cost.py's "soft preference, not hard filter" design.
_FALLBACK_LTS = 4

# Mirrors web/app.js's FACILITY_DASH_EXPRESSION exactly (same fields, same
# priority order: cycleway > path > street) - if that changes, update this
# too. Drives the road-type breakdown in the routing panel's summary bar.
_CYCLEWAY_RULES = {"s3", "s7", "s8"}
_PATH_HIGHWAYS = {"path", "track", "footway", "bridleway"}
_PATH_RULES = {"s1", "s2"}


def facility_code(highway, rule) -> int:
    """0=street, 1=cycleway, 2=path."""
    if highway == "cycleway" or rule in _CYCLEWAY_RULES:
        return 1
    if highway in _PATH_HIGHWAYS or rule in _PATH_RULES:
        return 2
    return 0


# Same 6 buckets as domain/lts_rules.py's BikePathAnalysis.slope_penalty
# pd.cut labels, coded as a compact u8 for the binary export (see
# encode_routing_graph_binary's layout comment) - keep in sync with
# domain/routing_cost.py's FATIGUE_PENALTY, which is keyed by these same
# label strings.
_SLOPE_CLASS_CODE = {
    "0-3: flat": 0,
    "3-5: mild": 1,
    "5-8: medium": 2,
    "8-10: hard": 3,
    "10-20: extreme": 4,
    ">20: impossible": 5,
}
# 255 = unknown/no reliable slope_class (NaN, or an unrecognized label) -
# NOT "flat" (code 0). domain/routing_cost.py's edge_cost only applies a
# fatigue multiplier for a recognized code; this value deliberately never
# matches one, so such an edge falls back to the neutral 1.0 multiplier,
# same treatment as "no slope data at all" rather than "measured flat".
UNKNOWN_SLOPE_CLASS_CODE = 255


def slope_class_code(value) -> int:
    if pd.isna(value):
        return UNKNOWN_SLOPE_CLASS_CODE
    return _SLOPE_CLASS_CODE.get(str(value), UNKNOWN_SLOPE_CLASS_CODE)


def _first_if_list(value):
    # `name` is occasionally list-valued in this project's OSM data, same
    # as `osmid` (see services/osm_pbf_service.py's own isinstance(..., list)
    # handling) - take the first value rather than choking on it.
    return value[0] if isinstance(value, list) else value


def build_routing_graph(edges_gdf: gpd.GeoDataFrame, nodes_df: pd.DataFrame, slug: str) -> dict:
    """`edges_gdf`: the raw (u, v, key)-indexed frame read straight from
    <slug>_all_lts.parquet - only `length`/`lts`/`istat_code` are read
    here, geometry/CRS are irrelevant to this export.
    `nodes_df`: a plain frame with `osmid`/`x`(lon)/`y`(lat) columns, read
    from <slug>_nodes.parquet.

    Returns the dict passed to encode_routing_graph_binary() (below), which
    writes the actual <slug>_routing.bin file:

        {
          "istat": "022205", "slug": "trento", "generated_at": "...",
          "nodes": [[lon, lat], ...],       # index-aligned with node_osm_ids
          "node_osm_ids": [123456789, ...], # cross-file join key
          "names": ["Via Roma", ...],       # interned street names
          "edges": [[u_idx, v_idx, lts, length_m, facility_code, name_idx,
                     slope_class_code], ...]
                                             # u_idx/v_idx are LOCAL to this
                                             # file's nodes; name_idx is
                                             # LOCAL to this file's names
                                             # (-1 = unnamed); slope_class_code
                                             # is UNKNOWN_SLOPE_CLASS_CODE
                                             # (255) when there's no
                                             # reliable slope reading
        }
    """
    node_xy = {int(osmid): (float(x), float(y)) for osmid, x, y in zip(nodes_df["osmid"], nodes_df["x"], nodes_df["y"])}

    nodes: list[list[float]] = []
    node_osm_ids: list[int] = []
    node_index_by_osm_id: dict[int, int] = {}
    names: list[str] = []
    name_index_by_value: dict[str, int] = {}
    edges: list[list] = []

    def node_index(osm_id):
        idx = node_index_by_osm_id.get(osm_id)
        if idx is not None:
            return idx
        xy = node_xy.get(osm_id)
        if xy is None:
            return None  # no known position for this node - can't place it
        idx = len(nodes)
        node_index_by_osm_id[osm_id] = idx
        nodes.append([round(xy[0], 6), round(xy[1], 6)])
        node_osm_ids.append(osm_id)
        return idx

    def name_index(name) -> int:
        name = _first_if_list(name)
        if pd.isna(name) or name == "":
            return -1
        idx = name_index_by_value.get(name)
        if idx is not None:
            return idx
        idx = len(names)
        name_index_by_value[name] = idx
        names.append(name)
        return idx

    has_highway = "highway" in edges_gdf.columns
    has_rule = "rule" in edges_gdf.columns
    has_name = "name" in edges_gdf.columns
    has_slope_class = "slope_class" in edges_gdf.columns
    for (u, v, _key), length, lts, highway, rule, name, slope_class in zip(
        edges_gdf.index,
        edges_gdf["length"],
        edges_gdf["lts"],
        edges_gdf["highway"] if has_highway else [None] * len(edges_gdf),
        edges_gdf["rule"] if has_rule else [None] * len(edges_gdf),
        edges_gdf["name"] if has_name else [None] * len(edges_gdf),
        edges_gdf["slope_class"] if has_slope_class else [None] * len(edges_gdf),
    ):
        if pd.isna(length):
            continue
        # LTS 0 means "not cyclable at all" (the LTS_COLORS/legend "Non
        # ciclabile" class - e.g. a motorway with no bike access), not
        # merely "very stressful". Treating it as just an expensive edge
        # (the old behaviour: LTS_PENALTY.get(lts, LTS_PENALTY[4]) falls
        # back to the LTS-4 rate for any unlisted class, 0 included) let
        # the router silently draw a route across a road a cyclist can't
        # actually use, instead of finding a real alternative or reporting
        # no route. Dropping the edge entirely - same treatment as "no
        # known position"/"null geometry" below - is the correct fix: it
        # was never a valid choice, not just a costly one. NaN `lts`
        # (unclassified, not explicitly 0) is unaffected and still falls
        # back to _FALLBACK_LTS, per the "soft preference" design.
        if not pd.isna(lts) and int(lts) == 0:
            continue
        u_idx = node_index(u)
        v_idx = node_index(v)
        if u_idx is None or v_idx is None:
            continue
        edge_lts = _FALLBACK_LTS if pd.isna(lts) else int(lts)
        edges.append(
            [
                u_idx,
                v_idx,
                edge_lts,
                round(float(length), 1),
                facility_code(highway, rule),
                name_index(name),
                slope_class_code(slope_class),
            ]
        )

    istat = edges_gdf["istat_code"].iloc[0] if "istat_code" in edges_gdf.columns and len(edges_gdf) else None
    return {
        "istat": istat,
        "slug": slug,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nodes": nodes,
        "node_osm_ids": node_osm_ids,
        "names": names,
        "edges": edges,
    }


# Compact binary wire format for <slug>_routing.bin, decoded by
# web/routing.js's decodeRoutingGraphBinary (that function's own comment
# has the identical layout description - keep both in sync). Chosen over
# a schema-compiler format (FlatBuffers etc.): this is a single-producer/
# single-consumer format with a schema that basically never changes, so
# the interop/versioning machinery those tools exist for buys nothing here
# - a hand-packed structure-of-arrays layout gets the same real win (zero-
# copy typed-array reads in the browser, no JSON.parse of a huge array-of-
# arrays, no text-encoding overhead on every float) with no new build
# tooling (numpy - already a dependency - does the packing).
#
# `istat`/`generated_at` are dropped here even though build_routing_graph()
# returns them - web/routing.js never reads either field (only `slug` is
# consumed, for comuneSlug), so shipping them would be dead weight on
# every fetch. Layout (all little-endian):
#
#   [u32]  headerLen = H
#   [H bytes] UTF-8 JSON: {"slug","names","nodeCount":NC,"edgeCount":EC}
#   [pad]  zero bytes up to the next 8-byte boundary (so nodeOsmIds below
#          can be read as a real Float64Array, which requires 8-byte
#          alignment - typed-array *construction* throws if the buffer
#          offset isn't a multiple of the element size, unlike DataView)
#   [f32 x NC] node longitudes
#   [f32 x NC] node latitudes
#   [f64 x NC] node OSM ids - float64, not a 32-bit int type: real OSM
#              node ids already sit close to the uint32 ceiling (~4.29e9)
#              and keep growing, but every id is comfortably inside
#              float64's 53-bit exact-integer range, and it keeps the JS
#              side a plain `number` (matching every other place in this
#              codebase an osmid is used as a Map key/ngraph node id),
#              no BigInt conversions needed anywhere.
#   [u32 x EC] edge u_idx      (LOCAL to this file's node array)
#   [u32 x EC] edge v_idx
#   [f32 x EC] edge length_m
#   [i32 x EC] edge name_idx   (signed - -1 means unnamed)
#   [u8  x EC] edge lts
#   [u8  x EC] edge facility_code
#   [u8  x EC] edge slope_class_code (255 = unknown, see UNKNOWN_SLOPE_CLASS_CODE)
#
# Field ORDER is load-bearing, not cosmetic: every multi-byte (4/8-byte)
# field comes before the three single-byte ones at the end. Uint8Array
# construction has no alignment requirement at all, so putting all 1-byte
# fields last means every section boundary in the whole body already
# lands on a valid 4-byte (or 8-byte, for the f64 id array) boundary by
# construction - NO padding is ever needed mid-body, only once, right
# after the header. Reordering these fields without updating
# decodeRoutingGraphBinary to match breaks silently (wrong values read
# from the wrong byte offsets), not with a thrown error - the whole point
# of typed-array views is that they trust the layout instead of checking it.
def encode_routing_graph_binary(result: dict) -> bytes:
    header = json.dumps(
        {
            "slug": result["slug"],
            "names": result["names"],
            "nodeCount": len(result["nodes"]),
            "edgeCount": len(result["edges"]),
        },
        separators=(",", ":"),
    ).encode("utf-8")

    nodes = result["nodes"]
    edges = result["edges"]
    node_lons = np.array([n[0] for n in nodes], dtype="<f4")
    node_lats = np.array([n[1] for n in nodes], dtype="<f4")
    node_osm_ids = np.array(result["node_osm_ids"], dtype="<f8")
    edge_u = np.array([e[0] for e in edges], dtype="<u4")
    edge_v = np.array([e[1] for e in edges], dtype="<u4")
    edge_length = np.array([e[3] for e in edges], dtype="<f4")
    edge_name_idx = np.array([e[5] for e in edges], dtype="<i4")
    edge_lts = np.array([e[2] for e in edges], dtype="<u1")
    edge_facility = np.array([e[4] for e in edges], dtype="<u1")
    edge_slope_class = np.array([e[6] for e in edges], dtype="<u1")

    header_len_prefix = struct.pack("<I", len(header))
    body_start = len(header_len_prefix) + len(header)
    padding = b"\x00" * ((-body_start) % 8)  # round up to the next 8-byte boundary

    body = b"".join(
        arr.tobytes()
        for arr in (
            node_lons,
            node_lats,
            node_osm_ids,
            edge_u,
            edge_v,
            edge_length,
            edge_name_idx,
            edge_lts,
            edge_facility,
            edge_slope_class,
        )
    )
    return header_len_prefix + header + padding + body


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: build_routing_graph.py <area_slug> [data_dir]", file=sys.stderr)
        sys.exit(1)
    slug = sys.argv[1]

    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    default_data_dir = os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    data_dir = sys.argv[2] if len(sys.argv) > 2 else default_data_dir

    parquet_path = os.path.join(data_dir, slug, f"{slug}_all_lts.parquet")
    nodes_path = os.path.join(data_dir, slug, f"{slug}_nodes.parquet")
    if not os.path.exists(parquet_path):
        print(f"ERROR: {parquet_path} not found - run compute-lts for {slug} first.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(nodes_path):
        print(
            f"ERROR: {nodes_path} not found - re-run compute-lts for {slug} "
            "(needs a version that exports node positions) before this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    edges_gdf = gpd.read_parquet(parquet_path)
    nodes_df = pd.read_parquet(nodes_path)
    result = build_routing_graph(edges_gdf, nodes_df, slug)

    web_data_dir = os.path.join(repo_root, "web", "data")
    os.makedirs(web_data_dir, exist_ok=True)
    out_path = os.path.join(web_data_dir, f"{slug}_routing.bin")
    binary = encode_routing_graph_binary(result)
    with open(out_path, "wb") as file_handle:
        file_handle.write(binary)

    print(f"Wrote {out_path} ({len(result['nodes'])} nodes, {len(result['edges'])} edges, {len(binary)} bytes)")


if __name__ == "__main__":
    main()
