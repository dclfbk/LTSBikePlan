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
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

import geopandas as gpd
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

    Returns the JSON-serializable dict written to <slug>_routing.json:

        {
          "istat": "022205", "slug": "trento", "generated_at": "...",
          "nodes": [[lon, lat], ...],       # index-aligned with node_osm_ids
          "node_osm_ids": [123456789, ...], # cross-file join key
          "names": ["Via Roma", ...],       # interned street names
          "edges": [[u_idx, v_idx, lts, length_m, facility_code, name_idx], ...]
                                             # u_idx/v_idx are LOCAL to this
                                             # file's nodes; name_idx is
                                             # LOCAL to this file's names
                                             # (-1 = unnamed)
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
    for (u, v, _key), length, lts, highway, rule, name in zip(
        edges_gdf.index,
        edges_gdf["length"],
        edges_gdf["lts"],
        edges_gdf["highway"] if has_highway else [None] * len(edges_gdf),
        edges_gdf["rule"] if has_rule else [None] * len(edges_gdf),
        edges_gdf["name"] if has_name else [None] * len(edges_gdf),
    ):
        if pd.isna(length):
            continue
        u_idx = node_index(u)
        v_idx = node_index(v)
        if u_idx is None or v_idx is None:
            continue
        edge_lts = _FALLBACK_LTS if pd.isna(lts) else int(lts)
        edges.append(
            [u_idx, v_idx, edge_lts, round(float(length), 1), facility_code(highway, rule), name_index(name)]
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
    out_path = os.path.join(web_data_dir, f"{slug}_routing.json")
    with open(out_path, "w") as file_handle:
        json.dump(result, file_handle, separators=(",", ":"))

    print(f"Wrote {out_path} ({len(result['nodes'])} nodes, {len(result['edges'])} edges)")


if __name__ == "__main__":
    main()
