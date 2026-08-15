from __future__ import annotations

import os
import pickle

import folium
import geopandas as gpd
from shapely.geometry import Point

from ltsbikeplan.domain.crs import chunked_to_crs


class PersistenceService:
    @staticmethod
    def save_pickle(gdf_nodes, gdf_edges, city: str, pickle_path: str) -> None:
        with open(pickle_path, "wb") as file_handle:
            pickle.dump((gdf_nodes, gdf_edges, city), file_handle)

    @staticmethod
    def ensure_city_folder(images_dir: str, city_sanitized: str) -> str:
        city_folder_path = os.path.join(images_dir, city_sanitized)
        os.makedirs(city_folder_path, exist_ok=True)
        return city_folder_path

    @staticmethod
    def save_slope_map(gdf_edges, output_path: str) -> None:
        projected_crs = gdf_edges.estimate_utm_crs() or gdf_edges.crs
        gdf_edges_projected = chunked_to_crs(gdf_edges, projected_crs)
        gdf_edges_wgs = chunked_to_crs(gdf_edges, "EPSG:4326")
        color_palette = ["#267300", "#70A800", "#FFAA00", "#E60000", "#A80000", "#730000"]
        slope_classes = ["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"]
        colors = dict(zip(slope_classes, color_palette))

        # Averaged in the projected (metric) CRS, then only the single
        # resulting point is reprojected to WGS84 - not every edge
        # centroid, which for a full-comune edge count would otherwise be
        # exactly the kind of large to_crs() call chunked_to_crs works
        # around elsewhere (see domain/crs.py), just for a map-centering
        # value that doesn't need per-point precision.
        projected_centroids = gdf_edges_projected.geometry.centroid
        mean_point = gpd.GeoSeries([Point(projected_centroids.x.mean(), projected_centroids.y.mean())], crs=gdf_edges_projected.crs).to_crs(
            epsg=4326
        ).iloc[0]
        mean_latitude = mean_point.y
        mean_longitude = mean_point.x
        map_osm = folium.Map(location=[mean_latitude, mean_longitude], zoom_start=11)

        for _, row in gdf_edges_wgs.iterrows():
            color = colors.get(str(row["slope_class"]), "#000000")
            folium.GeoJson(row["geometry"], style_function=lambda _, color=color: {"color": color}).add_to(map_osm)

        legend_html = """
<div style="position: fixed; top: 10px; right: 10px; z-index: 1000; background-color: white; padding: 5px; border: 1px solid grey; font-size: 12px;">
<p><b>Slope</b></p>
"""
        for slope_class, color in colors.items():
            legend_html += f'<p><i class="fa fa-square" style="color:{color};"></i> {slope_class}</p>'
        legend_html += "</div>"
        map_osm.get_root().html.add_child(folium.Element(legend_html))
        map_osm.save(output_path)
