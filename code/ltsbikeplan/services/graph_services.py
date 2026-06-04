from __future__ import annotations

import numpy as np
import geopandas as gpd
import osmnx as ox
from sklearn.neighbors import NearestNeighbors


class GraphLoaderService:
    def download_graph(self, city: str):
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
            "pedestrian",
            "steps",
            "track",
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
        gdf_projected = gdf_buildings.to_crs(gdf_buildings.estimate_utm_crs() or 32632)
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
        gdf_edges = gdf_edges.to_crs(target_crs)
        gdf_buildings = gdf_buildings.to_crs(target_crs)

        for index, edge in gdf_edges.iterrows():
            edge_centroid = edge.geometry.centroid
            buffer = edge_centroid.buffer(urban_threshold)
            buffer_gdf = gpd.GeoDataFrame(geometry=[buffer], crs=gdf_edges.crs)
            possible_matches = gpd.sjoin(gdf_buildings, buffer_gdf, how="inner", predicate="intersects")
            if not possible_matches.empty:
                gdf_edges.at[index, "context"] = "urban"

        return gdf_edges
