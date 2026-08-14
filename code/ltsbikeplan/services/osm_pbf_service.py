from __future__ import annotations

import json
import os
import subprocess
from typing import List, Optional, Tuple

import numpy as np
import requests

from ltsbikeplan.domain.area_spec import AreaSpec

# Extra OSM tags domain/lts_rules.py::BikePathAnalysis reads that pyrosm does
# NOT include in its default get_network() column set (verified against a
# live osmit-estratti extract: pyrosm only materializes a column if at least
# one feature in the file actually carries that tag, so it's safe/cheap to
# over-request here - absent tags simply don't produce a column).
EXTRA_NETWORK_ATTRIBUTES = [
    "footway",
    "service",
    "width",
    "est_width",
    "shoulder:access:bicycle",
    "cycleway",
    "cycleway:left",
    "cycleway:right",
    "cycleway:both",
    "cycleway:lane",
    "parking:lane",
    "parking:lane:left",
    "parking:lane:right",
    "parking:lane:both",
    "parking:condition",
]

# Columns BikePathAnalysis reads unconditionally (would KeyError, not just
# skip an optional rule, if absent). Applied as a safety net to both the
# pyrosm and osmnx ingestion paths. `service` is here because
# domain/lts_rules.py::mixed_traffic guards its first read of that column
# with `if "service" in gdf_edges.columns` but then reads it unconditionally
# a few lines later (parking_aisle/driveway conditions) - confirmed by a
# live pilot run (comune of Atrani) crashing with KeyError: 'service' once
# an area's OSM extract legitimately has no `service` tag anywhere.
#
# `surface`/`cycleway*`/`width`/`est_width` aren't read by BikePathAnalysis
# unconditionally, but ARE selected unconditionally by compute_lts.py's
# export_columns for the web viewer's popup - guaranteeing them here keeps
# that a single safety net instead of two.
REQUIRED_EDGE_COLUMNS = [
    "access",
    "highway",
    "oneway",
    "lanes",
    "maxspeed",
    "length",
    "geometry",
    "osmid",
    "service",
    "surface",
    "cycleway",
    "cycleway:left",
    "cycleway:right",
    "cycleway:both",
    "width",
    "est_width",
]


def download_pbf_extract(area: AreaSpec, cache_dir: str) -> str:
    if area.pbf_url is None:
        raise ValueError(f"AreaSpec {area.name!r} has no pbf_url (source={area.source})")
    pbf_dir = os.path.join(cache_dir, "_cache", "osm_pbf")
    os.makedirs(pbf_dir, exist_ok=True)
    key = area.istat_code or area.slug
    out_path = os.path.join(pbf_dir, f"{key}.osm.pbf")
    if os.path.exists(out_path):
        return out_path

    with requests.get(area.pbf_url, stream=True, timeout=300) as response:
        response.raise_for_status()
        with open(out_path, "wb") as file_handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file_handle.write(chunk)
    return out_path


def compute_bbox_from_pbf(pbf_path: str) -> Tuple[float, float, float, float]:
    """Returns (west, south, east, north) in EPSG:4326 via `osmium fileinfo`."""
    result = subprocess.run(
        ["osmium", "fileinfo", "-e", "-j", pbf_path],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)
    west, south, east, north = info["data"]["bbox"]
    return (west, south, east, north)


def normalize_edge_columns(gdf_edges, required_columns: Optional[List[str]] = None):
    """Fill in any column BikePathAnalysis may reference that isn't present.

    Needed regardless of ingestion source: pyrosm only materializes a tag
    column when present in the extract, and osmnx's Overpass responses can
    likewise vary by area/query. Filling with NaN reproduces the "column
    absent" behaviour lts_rules.py already handles via its own `if col in
    gdf.columns` checks and `_get_columns_by_prefix` scans.
    """
    columns = list(required_columns) if required_columns is not None else list(REQUIRED_EDGE_COLUMNS)
    gdf_edges = gdf_edges.copy()
    for column in columns:
        if column not in gdf_edges.columns:
            gdf_edges[column] = np.nan
    return gdf_edges


def normalize_node_columns(gdf_nodes):
    """domain/lts_rules.py::calculate_lts_nodes reads `row["highway"]`
    unconditionally (unlike its edge-side rules, which mostly guard column
    access). pyrosm never promotes a node's `highway` tag (traffic_signals,
    stop, crossing, ...) to a top-level column - it stays in the per-node
    `tags` dict - so this recovers it from there instead of just filling
    NaN, to keep traffic-signal/stop detection working the same as the
    osmnx path (where Overpass already returns `highway` as a real column).
    Confirmed via a live pilot run (comune of Atrani): without this,
    calculate_lts_nodes raises KeyError: 'highway' on every pyrosm-sourced
    area, not just an edge case.
    """
    gdf_nodes = gdf_nodes.copy()
    if "highway" not in gdf_nodes.columns:
        if "tags" in gdf_nodes.columns:
            gdf_nodes["highway"] = gdf_nodes["tags"].apply(lambda tags: tags.get("highway") if isinstance(tags, dict) else np.nan)
        else:
            gdf_nodes["highway"] = np.nan
    return gdf_nodes


class PyrosmGraphLoader:
    def load_network(self, pbf_path: str, network_type: str = "all"):
        """Returns (gdf_nodes, gdf_edges) shaped identically to
        GraphLoaderService.download_graph's output: routing through pyrosm's
        own `to_graph(..., graph_type="networkx")` + osmnx's `graph_to_gdfs`
        guarantees the same (u, v, key) edge index and `osmid` column name
        (verified: pyrosm's `id` column is renamed to `osmid` by osmnx here),
        so UrbanContextClassifier/SlopeService/BikePathAnalysis need no
        source-specific handling beyond `normalize_edge_columns`/
        `normalize_node_columns`.
        """
        import osmnx as ox
        import pyrosm

        osm = pyrosm.OSM(pbf_path)
        nodes, edges = osm.get_network(nodes=True, network_type=network_type, extra_attributes=EXTRA_NETWORK_ATTRIBUTES)
        graph = osm.to_graph(nodes, edges, graph_type="networkx")
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(graph)
        gdf_edges = normalize_edge_columns(gdf_edges)
        gdf_nodes = normalize_node_columns(gdf_nodes)
        return gdf_nodes, gdf_edges

    def load_buildings(self, pbf_path: str):
        import pyrosm

        osm = pyrosm.OSM(pbf_path)
        return osm.get_buildings()
