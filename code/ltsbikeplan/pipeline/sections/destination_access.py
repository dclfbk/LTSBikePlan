from __future__ import annotations

import os

import folium
import geopandas as gpd
import pandas as pd

from ltsbikeplan.utils import sanitize_city_name

from .common import city_output_dir


def _write_placeholder_html(path: str, title: str, details: str) -> None:
    with open(path, "w") as file_handle:
        file_handle.write(f"<html><body><h3>{title}</h3><p>{details}</p></body></html>")


def _map_center(all_lts_gdf: gpd.GeoDataFrame) -> list[float]:
    projected = all_lts_gdf.to_crs(all_lts_gdf.estimate_utm_crs() or all_lts_gdf.crs)
    center_point = gpd.GeoSeries([projected.unary_union.centroid], crs=projected.crs).to_crs(epsg=4326).iloc[0]
    return [center_point.y, center_point.x]


def run_destination_access(data_dir: str, images_dir: str, city: str) -> None:
    out_dir = city_output_dir(images_dir, city)
    city_name = sanitize_city_name(city)

    lts_csv = os.path.join(data_dir, f"{city_name}_all_lts.csv")
    population_candidates = [
        os.path.join(data_dir, "hexagon_destinations.csv"),
        os.path.join(data_dir, "hexagon_destinations.json"),
    ]
    population_file = next((p for p in population_candidates if os.path.exists(p)), None)

    if not os.path.exists(lts_csv) or population_file is None:
        _write_placeholder_html(
            os.path.join(out_dir, "hexagonal_grid_population.html"),
            "Destination access unavailable",
            "Missing required input files: city LTS CSV and/or destination-population dataset.",
        )
        _write_placeholder_html(
            os.path.join(out_dir, "bna_score_map.html"),
            "BNA score unavailable",
            "Missing required input files for BNA score map generation.",
        )
        return

    all_lts_df = pd.read_csv(lts_csv, low_memory=False)
    all_lts_gdf = gpd.GeoDataFrame(all_lts_df, geometry=gpd.GeoSeries.from_wkt(all_lts_df["geometry"]), crs="EPSG:32632")
    all_lts_wgs = all_lts_gdf.to_crs(4326)

    center = _map_center(all_lts_gdf)
    pop_map = folium.Map(location=center, zoom_start=11)
    folium.GeoJson(all_lts_wgs[["geometry"]].to_json(), name="LTS Network").add_to(pop_map)
    pop_map.save(os.path.join(out_dir, "hexagonal_grid_population.html"))

    bna_map = folium.Map(location=center, zoom_start=11)
    folium.GeoJson(all_lts_wgs[["geometry"]].to_json(), name="BNA proxy").add_to(bna_map)
    bna_map.save(os.path.join(out_dir, "bna_score_map.html"))
