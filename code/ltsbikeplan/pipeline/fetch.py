from __future__ import annotations

import os

from ltsbikeplan.services.graph_services import GraphLoaderService, UrbanContextClassifier
from ltsbikeplan.services.persistence_service import PersistenceService
from ltsbikeplan.services.slope_service import SlopeService
from ltsbikeplan.utils import sanitize_city_name


def run_fetch(city: str, data_dir: str, images_dir: str, dem_path: str, slope_strategy: str = "v3") -> None:
    city_sanitized = sanitize_city_name(city)
    graph_loader = GraphLoaderService()
    context_classifier = UrbanContextClassifier()
    persistence = PersistenceService()
    slope_service = SlopeService(strategy=slope_strategy)

    city_folder_path = persistence.ensure_city_folder(images_dir, city_sanitized)
    _, gdf_nodes, gdf_edges = graph_loader.download_graph(city)
    gdf_edges = graph_loader.filter_major_roads(gdf_edges)

    gdf_buildings = graph_loader.fetch_building_data(city)
    distances = context_classifier.calculate_building_distances(gdf_buildings)
    quintiles = context_classifier.divide_into_quintiles(distances)

    original_index = gdf_edges.index
    gdf_edges_projected = gdf_edges.to_crs(epsg=32632)
    gdf_edges_classified = context_classifier.classify_edges_by_quintiles(gdf_edges_projected, gdf_buildings, quintiles)
    gdf_edges = gdf_edges_classified.to_crs(gdf_edges.crs)

    gdf_edges = slope_service.apply(gdf_edges, dem_path)
    gdf_edges.index = original_index

    pickle_path = os.path.join(data_dir, "gdf_data.pkl")
    persistence.save_pickle(gdf_nodes, gdf_edges, city, pickle_path)
    persistence.save_slope_map(gdf_edges, os.path.join(city_folder_path, "slope_map.html"))
