from __future__ import annotations

import numpy as np
import geopandas as gpd
import osmnx as ox
from sklearn.neighbors import NearestNeighbors

from ltsbikeplan.domain.crs import WORKING_CRS, chunked_to_crs

# Tags BikePathAnalysis reads that aren't in osmnx's default
# useful_tags_way - without these, they'd silently never reach the domain
# rules that need them on the osmnx ingestion path (motorroad: trunk/
# trunk_link legally barred to bicycles; sac_scale/mtb:scale: mountain
# trails too technical for a city/e-bike despite being highway=path/footway).
_EXTRA_USEFUL_TAGS_WAY = ["motorroad", "sac_scale", "mtb:scale"]


class GraphLoaderService:
    def download_graph(self, city: str):
        missing_tags = [tag for tag in _EXTRA_USEFUL_TAGS_WAY if tag not in ox.settings.useful_tags_way]
        if missing_tags:
            ox.settings.useful_tags_way = ox.settings.useful_tags_way + missing_tags
        graph = ox.graph_from_place(city, network_type="all")
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(graph)
        return graph, gdf_nodes, gdf_edges

    def filter_major_roads(self, gdf_edges):
        major_roads = [
            "primary",
            "primary_link",
            "secondary",
            "secondary_link",
            "tertiary",
            "tertiary_link",
            "residential",
            "cycleway",
            "living_street",
            "unclassified",
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "pedestrian",
            "steps",
            "track",
            # footway/path/service used to be missing here, silently
            # dropping them before BikePathAnalysis ever saw them even
            # though the rest of the pipeline clearly expects them
            # (EXTRA_NETWORK_ATTRIBUTES fetches their tags, lts_rules.py
            # has dedicated rules for all three - is_separated_path's
            # s1/s2/s9 for footway/path, mixed_traffic's m2/m3/m4/m16 for
            # service). Confirmed empirically: a live Trento run produced
            # zero s1/s2/s9 edges before this fix.
            "footway",
            "path",
            "service",
        ]
        return gdf_edges[gdf_edges["highway"].isin(major_roads)]

    def fetch_building_data(self, city: str):
        print(f"Fetching building data for {city}...")
        buildings = ox.features_from_place(city, tags={"building": True})
        print(f"Number of buildings fetched: {len(buildings)}")
        return buildings


class UrbanContextClassifier:
    def calculate_building_distances(self, gdf_buildings):
        print(f"Calculating distances for {len(gdf_buildings)} buildings...")
        gdf_projected = gdf_buildings.to_crs(gdf_buildings.estimate_utm_crs() or WORKING_CRS)
        building_coords = np.array(list(gdf_projected.geometry.centroid.apply(lambda x: (x.x, x.y))))
        nbrs = NearestNeighbors(n_neighbors=2, algorithm="ball_tree").fit(building_coords)
        distances, _ = nbrs.kneighbors(building_coords)
        return distances[:, 1]

    def divide_into_quintiles(self, distances):
        return np.percentile(distances, [20, 40, 60, 80, 100])

    def classify_edges_by_quintiles(self, gdf_edges, gdf_buildings, quintiles):
        urban_threshold = quintiles[2]
        print(f"Urban threshold set at {urban_threshold} units")
        gdf_edges = gdf_edges.copy()
        gdf_edges["context"] = "countryside"
        target_crs = gdf_edges.estimate_utm_crs() or gdf_edges.crs
        gdf_edges = chunked_to_crs(gdf_edges, target_crs)
        gdf_buildings = gdf_buildings.to_crs(target_crs)

        for index, edge in gdf_edges.iterrows():
            edge_centroid = edge.geometry.centroid
            buffer = edge_centroid.buffer(urban_threshold)
            buffer_gdf = gpd.GeoDataFrame(geometry=[buffer], crs=gdf_edges.crs)
            possible_matches = gpd.sjoin(gdf_buildings, buffer_gdf, how="inner", predicate="intersects")
            if not possible_matches.empty:
                gdf_edges.at[index, "context"] = "urban"

        return gdf_edges
