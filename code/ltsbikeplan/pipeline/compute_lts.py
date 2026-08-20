from __future__ import annotations

import json
import os
import pickle
import uuid
import xml.etree.ElementTree as et

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd

from ltsbikeplan.assets import asset_path
from ltsbikeplan.domain.area_spec import AreaSpec
from ltsbikeplan.domain.area_statistics import compute_area_statistics
from ltsbikeplan.domain.crs import WORKING_CRS, chunked_to_crs
from ltsbikeplan.domain.gap_analysis import annotate_gap_components
from ltsbikeplan.domain.lts_rules import BikePathAnalysis
from ltsbikeplan.domain.network_centrality import annotate_edge_centrality
from ltsbikeplan.domain.parallel_cycleway import annotate_parallel_cycleway
from ltsbikeplan.services.export_service import ExportService

# Minimum low-stress "island" length for a high-stress edge touching it to
# count as a priority intervention candidate - without this, a 2-edge
# residential loop in an isolated hamlet competes equally with a 15km urban
# low-stress network. See domain/gap_analysis.py::annotate_gap_components.
MIN_GAP_ISLAND_LENGTH_KM = 1.0

# A gap edge running within this distance of a separated cycle path for at
# least PARALLEL_CYCLEWAY_COVERAGE_THRESHOLD of its length already has a
# low-stress alternative - riders take the parallel path, not the stressful
# street, so it's a weak priority-intervention candidate despite its high
# LTS. See domain/parallel_cycleway.py::annotate_parallel_cycleway.
PARALLEL_CYCLEWAY_BUFFER_M = 30.0
PARALLEL_CYCLEWAY_COVERAGE_THRESHOLD = 0.75

# Order matters: the first non-"no"/"none" value wins. The 4 raw OSM tags
# stay noisy/inconsistent for direct display (different tagging schemes put
# the cycleway type on different keys) - this collapses them into one field
# for the web viewer's popup, while the raw tags remain in the export for
# anyone who wants them.
_CYCLEWAY_TAG_PRIORITY = ("cycleway", "cycleway:both", "cycleway:right", "cycleway:left")


def derive_cycleway_type(row):
    for column in _CYCLEWAY_TAG_PRIORITY:
        value = row.get(column)
        if isinstance(value, str) and value not in ("no", "none"):
            return value
    return np.nan


def _save_and_correct_graphml(graph, filepath: str) -> None:
    temp_path = filepath + "_temp.graphml"
    ox.save_graphml(graph, temp_path)

    tree = et.parse(temp_path)
    root = tree.getroot()
    ns = {"graphml": "http://graphml.graphdrawing.org/xmlns"}

    for data in root.findall(".//graphml:data", ns):
        if data.text and data.text.endswith(".0"):
            try:
                data.text = str(int(float(data.text)))
            except Exception:
                pass
        if data.text == "nan" or data.text is None:
            data.text = str(abs(uuid.uuid4().int))

    for elem in root.iter():
        elem.tag = elem.tag.split("}")[-1]
    root.attrib["xmlns"] = "http://graphml.graphdrawing.org/xmlns"
    if "xmlns:ns0" in root.attrib:
        del root.attrib["xmlns:ns0"]

    tree.write(filepath, xml_declaration=True, encoding="utf-8", method="xml")
    os.remove(temp_path)


def run_compute_lts(data_dir: str, area: AreaSpec, include_report_exports: bool = False) -> str:
    area_slug = area.slug
    area_dir = os.path.join(data_dir, area_slug)
    os.makedirs(area_dir, exist_ok=True)
    pickle_path = os.path.join(area_dir, "gdf_data.pkl")
    with open(pickle_path, "rb") as file_handle:
        gdf_nodes, gdf_edges, city = pickle.load(file_handle)

    # osmnx's (u, v, key) MultiIndex comes out of graph traversal order, not
    # sorted - every `.loc[:, ...]` assignment throughout BikePathAnalysis
    # (lts_rules.py) below then re-triggers pandas' "indexing past lexsort
    # depth" PerformanceWarning, once per stage, on every single area.
    # Sorting once here (verified: has no effect on the actual LTS values,
    # just row order) covers all of them instead of chasing each call site.
    gdf_edges = gdf_edges.sort_index()

    # Captured before any pd.concat below, which drops GeoDataFrame/crs
    # metadata - this is the only reliable source of the edges' *actual*
    # CRS (whatever the DEM raster used by SlopeService was in), since the
    # code used to just relabel the concatenated result as EPSG:4326
    # without reprojecting (see the explicit reprojection at the bottom of
    # this function for the fix).
    source_edges_crs = gdf_edges.crs

    steps_edges, gdf_edges = BikePathAnalysis.steps_analysis(gdf_edges)
    gdf_allowed, gdf_not_allowed = BikePathAnalysis.biking_permitted(gdf_edges)
    separated_edges, unseparated_edges = BikePathAnalysis.is_separated_path(gdf_allowed)
    separated_edges = separated_edges.copy()
    # Plain column assignment (not `.loc[:, ...]`) - the latter raises
    # "cannot set a frame with no defined index and a scalar" on newer
    # pandas when separated_edges is empty, which is the common case for
    # small/rural areas with no dedicated cycleways (found running the
    # Atrani pilot after this refactor made per-comune runs routine).
    # "s9" (see BikePathAnalysis.is_separated_path) is a path/footway a
    # sac_scale tag marks as a genuine mountain trail, not a comfortable
    # dedicated facility - lts=0, same "not applicable" bucket as steps
    # without a ramp, rather than the lts=1 every other separated path
    # gets.
    separated_edges["lts"] = np.where(separated_edges["rule"] == "s9", 0, 1)

    to_analyze, no_lane = BikePathAnalysis.is_bike_lane(unseparated_edges)
    parking_detected, parking_not_detected = BikePathAnalysis.parking_present(to_analyze)
    parking_lts = BikePathAnalysis.bike_lane_analysis_with_parking(parking_detected)
    no_parking_lts = BikePathAnalysis.bike_lane_analysis_without_parking(parking_not_detected)
    lts_no_lane = BikePathAnalysis.mixed_traffic(no_lane)

    gdf_not_allowed = gdf_not_allowed.copy()
    gdf_not_allowed["lts"] = 0
    lts_frames = [
        frame
        for frame in [separated_edges, parking_lts, no_parking_lts, lts_no_lane, gdf_not_allowed, steps_edges]
        if not frame.empty and frame.notna().any().any()
    ]
    all_lts = pd.concat(lts_frames) if lts_frames else pd.DataFrame()
    all_lts = BikePathAnalysis.slope_penalty(all_lts)
    all_lts = BikePathAnalysis.surface_penalty(all_lts)

    with open(asset_path("LTS_decisionrule_dict.json"), "r") as file_handle:
        data = json.load(file_handle)
    all_lts["message"] = all_lts["rule"].map(data["rule_message_dict"])
    all_lts["short_message"] = all_lts["rule"].map(data["simplified_message_dict"])

    # Fields for the web viewer's click popup - "" not None for istat_code
    # so it doesn't hit _save_and_correct_graphml's NaN/None-replacement
    # below for areas resolved via --city (no ISTAT code available).
    all_lts["comune"] = area.name
    all_lts["istat_code"] = area.istat_code or ""
    all_lts["cycleway_type"] = all_lts.apply(derive_cycleway_type, axis=1)
    all_lts = annotate_gap_components(all_lts, area_slug, min_island_length_km=MIN_GAP_ISLAND_LENGTH_KM)
    all_lts = annotate_edge_centrality(all_lts)

    # Reproject to the single internal working CRS instead of relabeling the
    # concatenated frame as EPSG:4326 without transforming coordinates - the
    # previous behaviour only "worked" because every hardcoded EPSG:32632
    # read-back elsewhere (maps.py, destination_access.py) happened to match
    # the DEM tile used for Trento. See domain/crs.py. Done before the
    # parallel-cycleway step below (moved ahead of the CSV export further
    # down for this reason) because that step buffers geometry by a metric
    # distance and needs real meters, not the source lon/lat CRS.
    all_lts = gpd.GeoDataFrame(all_lts, geometry="geometry", crs=source_edges_crs)
    all_lts = chunked_to_crs(all_lts, WORKING_CRS)
    all_lts = annotate_parallel_cycleway(
        all_lts,
        buffer_m=PARALLEL_CYCLEWAY_BUFFER_M,
        coverage_threshold=PARALLEL_CYCLEWAY_COVERAGE_THRESHOLD,
    )

    lts_parquet = os.path.join(area_dir, f"{area_slug}_all_lts.parquet")
    lts_geojson = os.path.join(area_dir, f"{area_slug}_all_lts.geojson")
    stats_json = os.path.join(area_dir, f"{area_slug}_stats.json")

    export_columns = [
        "osmid",
        "lanes",
        "name",
        "highway",
        "maxspeed",
        "geometry",
        "length",
        "rule",
        "lts",
        "slope",
        "slope_class",
        "lanes_assumed",
        "maxspeed_assumed",
        "message",
        "short_message",
        "comune",
        "istat_code",
        "surface",
        "surface_penalty_delta",
        "cycleway_type",
        "gap_component",
        "is_gap_edge",
        "gap_connects",
        "centrality",
        "centrality_class",
        "parallel_cycleway_coverage",
        "has_parallel_cycleway",
    ]

    if include_report_exports:
        nodes_csv = os.path.join(area_dir, f"{area_slug}_gdf_nodes.csv")
        lts_csv = os.path.join(area_dir, f"{area_slug}_all_lts.csv")
        gdf_nodes = gdf_nodes.copy()
        gdf_nodes["lts"], gdf_nodes["message"] = zip(*gdf_nodes.apply(BikePathAnalysis.calculate_lts_nodes, args=(all_lts,), axis=1))
        gdf_nodes.to_csv(nodes_csv)
        all_lts[export_columns].to_csv(lts_csv)

    ExportService.write_geoparquet(all_lts[export_columns], lts_parquet)
    ExportService.write_geojson(all_lts[export_columns], lts_geojson)

    # Per-area indicators for web/comuni.html's cross-comune comparison page
    # - istat_code/comune added here (not part of compute_area_statistics'
    # own LTS-derived indicators) so scripts/build_comuni_stats.py can join
    # against the ISTAT registry without re-deriving them from all_lts.
    area_statistics = compute_area_statistics(all_lts, area_slug)
    area_statistics["istat_code"] = area.istat_code or ""
    area_statistics["comune"] = area.name
    with open(stats_json, "w") as file_handle:
        json.dump(area_statistics, file_handle)

    if include_report_exports:
        # gdf_nodes was never reprojected (SlopeService only touches edges),
        # so its `geometry` column is still in the graph's original CRS
        # (EPSG:4326) while `all_lts` is now in WORKING_CRS. graph_from_gdfs
        # positions nodes from their `x`/`y` columns (not `geometry`), so
        # both must be updated explicitly to keep nodes and edges spatially
        # consistent in the export.
        graphml_path = os.path.join(area_dir, f"{area_slug}_lts.graphml")
        gdf_nodes = chunked_to_crs(gdf_nodes, WORKING_CRS)
        gdf_nodes["x"] = gdf_nodes.geometry.x
        gdf_nodes["y"] = gdf_nodes.geometry.y

        graph = ox.graph_from_gdfs(
            gdf_nodes,
            all_lts[export_columns],
        )
        _save_and_correct_graphml(graph, graphml_path)

    os.remove(pickle_path)
    return city
