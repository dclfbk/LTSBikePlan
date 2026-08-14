from __future__ import annotations

import os

import folium
import geopandas as gpd
import pandas as pd


def _load_lts_data(data_dir: str, area_slug: str) -> gpd.GeoDataFrame:
    parquet_path = os.path.join(data_dir, area_slug, f"{area_slug}_all_lts.parquet")
    all_lts = gpd.read_parquet(parquet_path)
    return all_lts.to_crs(epsg=4326)


def _map_center(all_lts: gpd.GeoDataFrame) -> list[float]:
    projected = all_lts.to_crs(all_lts.estimate_utm_crs() or all_lts.crs)
    center_point = gpd.GeoSeries([projected.unary_union.centroid], crs=projected.crs).to_crs(epsg=4326).iloc[0]
    return [center_point.y, center_point.x]


def generate_lts_map(data_dir: str, images_dir: str, area_slug: str) -> None:
    city_folder = os.path.join(images_dir, area_slug)
    os.makedirs(city_folder, exist_ok=True)

    all_lts = _load_lts_data(data_dir, area_slug)
    color_palette = ["forestgreen", "dodgerblue", "#f4e800", "firebrick", "#000000"]
    lts_classes = [1, 2, 3, 4, 0]
    colors = dict(zip(lts_classes, color_palette))

    center = _map_center(all_lts)
    fmap = folium.Map(location=center, zoom_start=11.5)

    for _, row in all_lts.iterrows():
        color = colors.get(int(row["lts"]) if pd.notna(row["lts"]) else 0, "#8c8c8c")
        folium.GeoJson(row["geometry"], style_function=lambda _, color=color: {"color": color, "weight": 3}).add_to(fmap)

    fmap.save(os.path.join(city_folder, "lts_map.html"))


def generate_h3_choropleth_map(data_dir: str, images_dir: str, area_slug: str) -> None:
    city_folder = os.path.join(images_dir, area_slug)
    os.makedirs(city_folder, exist_ok=True)

    all_lts = _load_lts_data(data_dir, area_slug)
    projected = all_lts.to_crs(all_lts.estimate_utm_crs() or all_lts.crs)
    lon_lat = gpd.GeoSeries(projected.geometry.centroid, crs=projected.crs).to_crs(epsg=4326)
    all_lts["lon"] = lon_lat.x
    all_lts["lat"] = lon_lat.y

    bins = pd.cut(all_lts["lts"].fillna(0), bins=[-1, 1.5, 2.5, 3.5, 4.5], labels=[1, 2, 3, 4]).astype(str)
    all_lts["lts_class"] = bins

    fmap = folium.Map(location=[all_lts["lat"].mean(), all_lts["lon"].mean()], zoom_start=11.5)
    color_map = {"1": "#2ca25f", "2": "#99d8c9", "3": "#fdae6b", "4": "#de2d26", "nan": "#969696"}

    for _, row in all_lts.iterrows():
        color = color_map.get(row["lts_class"], "#969696")
        folium.GeoJson(row["geometry"], style_function=lambda _, color=color: {"color": color, "weight": 2}).add_to(fmap)

    fmap.save(os.path.join(city_folder, "choropleth_lts_map.html"))
