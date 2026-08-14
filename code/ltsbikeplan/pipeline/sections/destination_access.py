from __future__ import annotations

import os

import folium
import geopandas as gpd

from .common import city_output_dir


def _write_placeholder_html(path: str, title: str, details: str) -> None:
    with open(path, "w") as file_handle:
        file_handle.write(f"<html><body><h3>{title}</h3><p>{details}</p></body></html>")


def _map_center(all_lts_gdf: gpd.GeoDataFrame) -> list[float]:
    projected = all_lts_gdf.to_crs(all_lts_gdf.estimate_utm_crs() or all_lts_gdf.crs)
    center_point = gpd.GeoSeries([projected.unary_union.centroid], crs=projected.crs).to_crs(epsg=4326).iloc[0]
    return [center_point.y, center_point.x]


def run_destination_access(data_dir: str, images_dir: str, area_slug: str) -> None:
    out_dir = city_output_dir(images_dir, area_slug)

    lts_parquet = os.path.join(data_dir, area_slug, f"{area_slug}_all_lts.parquet")
    population_candidates = [
        os.path.join(data_dir, "hexagon_destinations.csv"),
        os.path.join(data_dir, "hexagon_destinations.json"),
    ]
    population_file = next((p for p in population_candidates if os.path.exists(p)), None)

    if not os.path.exists(lts_parquet) or population_file is None:
        _write_placeholder_html(
            os.path.join(out_dir, "hexagonal_grid_population.html"),
            "Destination access unavailable",
            "Missing required input files: area LTS export and/or destination-population dataset.",
        )
        _write_placeholder_html(
            os.path.join(out_dir, "bna_score_map.html"),
            "BNA score unavailable",
            "Missing required input files for BNA score map generation.",
        )
        return

    all_lts_gdf = gpd.read_parquet(lts_parquet)
    all_lts_wgs = all_lts_gdf.to_crs(4326)

    center = _map_center(all_lts_gdf)
    pop_map = folium.Map(location=center, zoom_start=11)
    folium.GeoJson(all_lts_wgs[["geometry"]].to_json(), name="LTS Network").add_to(pop_map)
    pop_map.save(os.path.join(out_dir, "hexagonal_grid_population.html"))

    bna_map = folium.Map(location=center, zoom_start=11)
    folium.GeoJson(all_lts_wgs[["geometry"]].to_json(), name="BNA proxy").add_to(bna_map)
    bna_map.save(os.path.join(out_dir, "bna_score_map.html"))
