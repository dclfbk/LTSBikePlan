from __future__ import annotations

import os
from typing import Optional

from ltsbikeplan.domain.area_spec import AreaSpec
from ltsbikeplan.domain.crs import WORKING_CRS, chunked_to_crs
from ltsbikeplan.services.dem_service import MapterhornDemService
from ltsbikeplan.services.graph_services import GraphLoaderService, UrbanContextClassifier
from ltsbikeplan.services.osm_pbf_service import (
    PyrosmGraphLoader,
    apply_route_name_fallback,
    download_pbf_extract,
    extract_bicycle_route_names,
    normalize_edge_columns,
)
from ltsbikeplan.services.persistence_service import PersistenceService
from ltsbikeplan.services.slope_service import SlopeService


def _load_network(area: AreaSpec, cache_dir: str):
    """Returns (gdf_nodes, gdf_edges, gdf_buildings, area) - `area` is
    returned back out because the osmit path fills in `area.bbox` (needed
    for the Mapterhorn DEM fetch below) as a side effect of downloading the
    .osm.pbf extract.
    """
    graph_loader = GraphLoaderService()

    if area.source == "osmnx":
        _, gdf_nodes, gdf_edges = graph_loader.download_graph(area.place_query)
        gdf_edges = graph_loader.filter_major_roads(gdf_edges)
        gdf_edges = normalize_edge_columns(gdf_edges)
        gdf_buildings = graph_loader.fetch_building_data(area.place_query)
        if area.bbox is None:
            # osmnx/graph_to_gdfs keeps the EPSG:4326 default CRS, so
            # total_bounds is already (west, south, east, north) - same
            # convention as the osmit branch below, needed for the
            # Mapterhorn DEM auto-fetch.
            west, south, east, north = gdf_edges.total_bounds
            area = area.with_bbox((west, south, east, north))
        return gdf_nodes, gdf_edges, gdf_buildings, area

    pbf_path = download_pbf_extract(area, cache_dir)

    pyrosm_loader = PyrosmGraphLoader()
    gdf_nodes, gdf_edges = pyrosm_loader.load_network(pbf_path)
    gdf_edges = graph_loader.filter_major_roads(gdf_edges)
    if area.bbox is None:
        # From the filtered road network, NOT the raw .osm.pbf's own extent:
        # osmit-estratti extracts include every relation touching the
        # comune, e.g. Lampedusa e Linosa's extract also carries the
        # "Porto Empedocle - Linosa - Lampedusa" ferry route relation, whose
        # line runs to the Sicilian mainland - that stretched the file's own
        # bbox to ~110km x 200km (should be a couple km across two small
        # islands) and OOM-killed the Mapterhorn DEM mosaic/slope-gradient
        # step in production. Roads, not ferry routes, are what actually
        # need DEM coverage for slope - bound on gdf_edges instead, same as
        # the osmnx branch above.
        west, south, east, north = gdf_edges.total_bounds
        area = area.with_bbox((west, south, east, north))
    # osmit-estratti-only (pyrosm) - osmnx's Overpass responses above don't
    # expose relation membership the same way, so the osmnx branch has no
    # equivalent fallback. See extract_bicycle_route_names for why this
    # matters: some cycle networks (Trento's "Bicipolitana") put the only
    # human-legible name on the route relation, not the way.
    route_names = extract_bicycle_route_names(pbf_path)
    gdf_edges = apply_route_name_fallback(gdf_edges, route_names)
    gdf_buildings = pyrosm_loader.load_buildings(pbf_path)
    return gdf_nodes, gdf_edges, gdf_buildings, area


def _resolve_dem_path(area: AreaSpec, dem_path: Optional[str], cache_dir: str) -> str:
    if dem_path and os.path.exists(dem_path):
        return dem_path

    if area.bbox is None:
        raise ValueError(f"Cannot auto-fetch a DEM for area {area.name!r}: no bounding box available")

    dem_cache_dir = os.path.join(cache_dir, "_cache", "mapterhorn_tiles")
    out_path = os.path.join(cache_dir, "_cache", "dem", f"{area.slug}_mapterhorn.tif")
    if os.path.exists(out_path):
        return out_path

    dem_service = MapterhornDemService(cache_dir=dem_cache_dir)
    return dem_service.fetch_dem(area.bbox, out_path)


def run_fetch(area: AreaSpec, data_dir: str, images_dir: str, dem_path: Optional[str], slope_strategy: str = "v3") -> None:
    context_classifier = UrbanContextClassifier()
    persistence = PersistenceService()
    slope_service = SlopeService(strategy=slope_strategy)

    area_folder_path = persistence.ensure_city_folder(images_dir, area.slug)
    gdf_nodes, gdf_edges, gdf_buildings, area = _load_network(area, data_dir)

    distances = context_classifier.calculate_building_distances(gdf_buildings)
    quintiles = context_classifier.divide_into_quintiles(distances)

    original_index = gdf_edges.index
    gdf_edges_projected = chunked_to_crs(gdf_edges, WORKING_CRS)
    gdf_edges_classified = context_classifier.classify_edges_by_quintiles(gdf_edges_projected, gdf_buildings, quintiles)
    gdf_edges = chunked_to_crs(gdf_edges_classified, gdf_edges.crs)

    resolved_dem_path = _resolve_dem_path(area, dem_path, data_dir)
    gdf_edges = slope_service.apply(gdf_edges, resolved_dem_path)
    gdf_edges.index = original_index

    area_dir = os.path.join(data_dir, area.slug)
    os.makedirs(area_dir, exist_ok=True)
    pickle_path = os.path.join(area_dir, "gdf_data.pkl")
    persistence.save_pickle(gdf_nodes, gdf_edges, area.name, pickle_path)
    persistence.save_slope_map(gdf_edges, os.path.join(area_folder_path, "slope_map.html"))
