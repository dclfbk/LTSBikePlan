from __future__ import annotations

import json
import os
import pickle
import uuid
import xml.etree.ElementTree as et

import geopandas as gpd
import osmnx as ox
import pandas as pd

from ltsbikeplan.assets import asset_path
from ltsbikeplan.domain.lts_rules import BikePathAnalysis
from ltsbikeplan.utils import sanitize_city_name


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


def run_compute_lts(data_dir: str) -> str:
    pickle_path = os.path.join(data_dir, "gdf_data.pkl")
    with open(pickle_path, "rb") as file_handle:
        gdf_nodes, gdf_edges, city = pickle.load(file_handle)

    gdf_allowed, gdf_not_allowed = BikePathAnalysis.biking_permitted(gdf_edges)
    separated_edges, unseparated_edges = BikePathAnalysis.is_separated_path(gdf_allowed)
    separated_edges = separated_edges.copy()
    separated_edges.loc[:, "lts"] = 1

    to_analyze, no_lane = BikePathAnalysis.is_bike_lane(unseparated_edges)
    parking_detected, parking_not_detected = BikePathAnalysis.parking_present(to_analyze)
    parking_lts = BikePathAnalysis.bike_lane_analysis_with_parking(parking_detected)
    no_parking_lts = BikePathAnalysis.bike_lane_analysis_without_parking(parking_not_detected)
    lts_no_lane = BikePathAnalysis.mixed_traffic(no_lane)

    gdf_not_allowed = gdf_not_allowed.copy()
    gdf_not_allowed["lts"] = 0
    lts_frames = [
        frame
        for frame in [separated_edges, parking_lts, no_parking_lts, lts_no_lane, gdf_not_allowed]
        if not frame.empty and frame.notna().any().any()
    ]
    all_lts = pd.concat(lts_frames) if lts_frames else pd.DataFrame()
    all_lts = BikePathAnalysis.slope_penalty(all_lts)

    with open(asset_path("LTS_decisionrule_dict.json"), "r") as file_handle:
        data = json.load(file_handle)
    all_lts["message"] = all_lts["rule"].map(data["rule_message_dict"])
    all_lts["short_message"] = all_lts["rule"].map(data["simplified_message_dict"])

    gdf_nodes = gdf_nodes.copy()
    gdf_nodes["lts"], gdf_nodes["message"] = zip(*gdf_nodes.apply(BikePathAnalysis.calculate_lts_nodes, args=(all_lts,), axis=1))

    city_sanitized = sanitize_city_name(city)
    nodes_csv = os.path.join(data_dir, f"{city_sanitized}_gdf_nodes.csv")
    lts_csv = os.path.join(data_dir, f"{city_sanitized}_all_lts.csv")
    graphml_path = os.path.join(data_dir, f"{city_sanitized}_lts.graphml")

    gdf_nodes.to_csv(nodes_csv)
    all_lts[
        [
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
        ]
    ].to_csv(lts_csv)

    all_lts = gpd.GeoDataFrame(all_lts, geometry="geometry")
    all_lts.crs = "EPSG:4326"
    graph = ox.graph_from_gdfs(
        gdf_nodes,
        all_lts[
            [
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
            ]
        ],
    )
    _save_and_correct_graphml(graph, graphml_path)

    os.remove(pickle_path)
    return city
