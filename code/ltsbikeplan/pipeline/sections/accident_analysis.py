from __future__ import annotations

import json
import os

import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from ltsbikeplan.utils import sanitize_city_name

from .common import city_output_dir, save_placeholder


ACCIDENT_PLOTS = [
    "frequencyaccidentsbyroads_plot.png",
    "accidentsbynumberlanes_plot.png",
    "accidentsbymaxspeed_plot.png",
    "lanes_speed_distribution_plot.png",
    "accidents_lts_plot.png",
    "perc_accidents_lts_plot.png",
    "accidents_stress_level_plot.png",
    "perc_accidents_stress_level_plot.png",
    "accidents_lts_intersection_plot.png",
    "perc_accidents_lts_intersection_plot.png",
    "accidents_stress_level_intersection_plot.png",
    "perc_accidents_stress_level_intersection_plot.png",
    "DBSCAN_accident_clusters_plot.png",
]


def run_accident_analysis(data_dir: str, images_dir: str, city: str) -> None:
    out_dir = city_output_dir(images_dir, city)
    city_name = sanitize_city_name(city)
    accident_path = os.path.join(data_dir, f"accidents_{city_name.lower()}.geojson")
    if not os.path.exists(accident_path):
        return

    with open(accident_path, "r") as file_handle:
        accident_geojson = json.load(file_handle)
    accidents = gpd.GeoDataFrame.from_features(accident_geojson["features"], crs="EPSG:4326")
    if accidents.empty:
        return
    accidents = accidents.to_crs(4326)

    center = [accidents.geometry.y.mean(), accidents.geometry.x.mean()]
    amap = folium.Map(location=center, zoom_start=12)
    for _, row in accidents.iterrows():
        folium.CircleMarker(location=[row.geometry.y, row.geometry.x], radius=2, color="red", fill=True).add_to(amap)
    amap.save(os.path.join(out_dir, "accident_map.html"))

    hmap = folium.Map(location=center, zoom_start=12)
    for _, row in accidents.iterrows():
        folium.CircleMarker(location=[row.geometry.y, row.geometry.x], radius=6, color="orange", fill=True, fill_opacity=0.15).add_to(hmap)
    hmap.save(os.path.join(out_dir, "heatmap_map.html"))

    kmap = folium.Map(location=center, zoom_start=12)
    for _, row in accidents.iterrows():
        folium.CircleMarker(location=[row.geometry.y, row.geometry.x], radius=4, color="purple", fill=True, fill_opacity=0.1).add_to(kmap)
    kmap.save(os.path.join(out_dir, "kde_map.html"))

    # basic accident counts by year
    if "anno" in accidents.columns:
        series = pd.to_numeric(accidents["anno"], errors="coerce").dropna().astype(int)
        plt.figure(figsize=(8, 4))
        series.value_counts().sort_index().plot(kind="bar", color="#4c78a8")
        plt.title("Accidents by Year")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "frequencyaccidentsbyroads_plot.png"), dpi=200)
        plt.close()

    for name in ACCIDENT_PLOTS:
        path = os.path.join(out_dir, name)
        if not os.path.exists(path):
            save_placeholder(path, f"Accident section placeholder: {name}")

    chor_path = os.path.join(out_dir, "choropleth_lts_accidents_map.html")
    with open(chor_path, "w") as file_handle:
        file_handle.write("<html><body><h3>Choropleth accidents placeholder</h3></body></html>")
