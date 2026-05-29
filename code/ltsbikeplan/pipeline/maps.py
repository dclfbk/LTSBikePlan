from __future__ import annotations

import os

import folium
import geopandas as gpd
import pandas as pd
from shapely import wkt

from ltsbikeplan.utils import sanitize_city_name


def _load_lts_data(data_dir: str, city: str) -> gpd.GeoDataFrame:
    city_sanitized = sanitize_city_name(city)
    all_lts_df = pd.read_csv(os.path.join(data_dir, f"{city_sanitized}_all_lts.csv"))
    all_lts_df["geometry"] = all_lts_df["geometry"].apply(wkt.loads)
    all_lts = gpd.GeoDataFrame(all_lts_df, geometry="geometry", crs="EPSG:32632")
    return all_lts.to_crs(epsg=4326)


def generate_lts_map(data_dir: str, images_dir: str, city: str) -> None:
    city_sanitized = sanitize_city_name(city)
    city_folder = os.path.join(images_dir, city_sanitized)
    os.makedirs(city_folder, exist_ok=True)

    all_lts = _load_lts_data(data_dir, city)
    color_palette = ["forestgreen", "dodgerblue", "#f4e800", "firebrick", "#000000"]
    lts_classes = [1, 2, 3, 4, 0]
    colors = dict(zip(lts_classes, color_palette))

    center = [all_lts.geometry.centroid.y.mean(), all_lts.geometry.centroid.x.mean()]
    fmap = folium.Map(location=center, zoom_start=11.5)

    for _, row in all_lts.iterrows():
        color = colors.get(int(row["lts"]) if pd.notna(row["lts"]) else 0, "#8c8c8c")
        folium.GeoJson(row["geometry"], style_function=lambda _, color=color: {"color": color, "weight": 3}).add_to(fmap)

    fmap.save(os.path.join(city_folder, "lts_map.html"))


def generate_h3_choropleth_map(data_dir: str, images_dir: str, city: str) -> None:
    city_sanitized = sanitize_city_name(city)
    city_folder = os.path.join(images_dir, city_sanitized)
    os.makedirs(city_folder, exist_ok=True)

    all_lts = _load_lts_data(data_dir, city)
    all_lts["lon"] = all_lts.geometry.centroid.x
    all_lts["lat"] = all_lts.geometry.centroid.y

    bins = pd.cut(all_lts["lts"].fillna(0), bins=[-1, 1.5, 2.5, 3.5, 4.5], labels=[1, 2, 3, 4]).astype(str)
    all_lts["lts_class"] = bins

    fmap = folium.Map(location=[all_lts["lat"].mean(), all_lts["lon"].mean()], zoom_start=11.5)
    color_map = {"1": "#2ca25f", "2": "#99d8c9", "3": "#fdae6b", "4": "#de2d26", "nan": "#969696"}

    for _, row in all_lts.iterrows():
        color = color_map.get(row["lts_class"], "#969696")
        folium.GeoJson(row["geometry"], style_function=lambda _, color=color: {"color": color, "weight": 2}).add_to(fmap)

    fmap.save(os.path.join(city_folder, "choropleth_lts_map.html"))
