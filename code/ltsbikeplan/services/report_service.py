from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportContext:
    city_sanitized: str
    data_dir: str
    code_dir: str
    images_dir: str

    @property
    def city_img_path(self) -> str:
        return os.path.join(self.images_dir, self.city_sanitized)


class ReportService:
    LTS_IMAGES = ["slope_map.html", "lts_map.html", "choropleth_lts_map.html"]
    ESDA_IMAGES = ["network_base.png", "streetnetworkorientation_plot.png", "sno_polar_plot.png"]
    NETWORK_IMAGES = [
        "nodes_degree_centrality.png",
        "nodes_closeness_centrality.png",
        "nodes_betweenness_centrality.png",
        "edge_betweenness_centrality.png",
        "lts_distrib_nodes_plot.png",
        "lts_distrib_edges_plot.png",
        "nodess_betweenness_centrality.png",
        "nodess_closeness_centrality.png",
        "nodess_betweenness_centrality.png",
        "edgez_betweenness_centrality.png",
        "deg_central_map.png",
        "deg_central_map_top_nodes.png",
        "clos_central_map.png",
        "clos_central_map_top_nodes.png",
        "betw_central_map.png",
        "betw_central_map_top_nodes.png",
        "edge_bet_central_map.png",
        "edge_bet_central_map_top_nodes.png",
        "g_high_stres_map.png",
        "component_1.png",
        "component_2.png",
        "component_3.png",
        "component_4.png",
        "component_5.png",
        "kde_est_simplifiedgraph.png",
        "nearest_poi_plot.png",
    ]
    CLUSTER_IMAGES = [
        "dbscan_lts_cluster_geo.png",
        "dbscan_lts_cluster.png",
        "hdbscan_lts_cluster_geo.png",
        "hdbscan_lts_cluster.png",
        "optics_lts_cluster_geo.png",
        "optics_lts_cluster.png",
    ]
    GAP_IMAGES = [
        "Top10connectedcomponents_plot.png",
        "highlowstresscomponents_plot.png",
        "gaps_plot.png",
        "contact_nodes_plot.png",
        "heter_gapclosure_benefits.png",
        "gaps_classified_plot.html",
    ]
    DA_IMAGES = ["hexagonal_grid_population.html", "bna_score_map.html"]
    SUMUP_IMAGES = ["gap_quadrants.html", "risk_accidents_hexagon.html"]
    ACCIDENT_IMAGES = [
        "accident_map.html",
        "heatmap_map.html",
        "kde_map.html",
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
        "choropleth_lts_accidents_map.html",
    ]

    @staticmethod
    def _image_paths(city_img_path: str, image_names: list[str]) -> list[str]:
        return [os.path.join(city_img_path, image_name) for image_name in image_names]

    @staticmethod
    def _render_image_section(title: str, paths: list[str]) -> str:
        body = "\n".join([f"![{os.path.basename(path)}]({path})\n" for path in paths])
        return f"## {title}\n\n{body}\n"

    @staticmethod
    def _existing_paths(paths: list[str]) -> list[str]:
        return [path for path in paths if os.path.exists(path)]

    @staticmethod
    def has_accident_data(city_sanitized: str, data_dir: str) -> bool:
        candidates = [
            os.path.join(data_dir, f"accidents_{city_sanitized.lower()}.geojson"),
            os.path.join(data_dir, f"accidents_{city_sanitized}.geojson"),
        ]
        return any(os.path.exists(candidate) for candidate in candidates)

    def build_markdown(self, context: ReportContext) -> str:
        city_img_path = context.city_img_path

        sections = [
            f"""
<div class='blue-stripe-header'>
<h2>{context.city_sanitized} - Level of Traffic Stress Bike Planning and Infrastructure Network Analysis for Safe and Accessible Cycling</h2>
</div>

## Introduction

<div class='introduction-text'>
This report offers an in-depth analysis of a selected region's road network, focusing on the Level of Traffic Stress (LTS) and its relation to perceived risk.
</div>
""",
        ]

        section_specs = [
            ("Section 1: Slope and Level of Traffic Stress", self.LTS_IMAGES),
            ("Section 2: Exploratory Spatial Data Analysis", self.ESDA_IMAGES),
            ("Section 3: Cluster Analysis", self.CLUSTER_IMAGES),
            ("Section 4: Network Analysis", self.NETWORK_IMAGES),
            ("Section 5: Gap Analysis", self.GAP_IMAGES),
            ("Section 6: Destination Access Analysis", self.DA_IMAGES),
        ]
        for title, images in section_specs:
            paths = self._existing_paths(self._image_paths(city_img_path, images))
            if paths:
                sections.append(self._render_image_section(title, paths))

        if self.has_accident_data(context.city_sanitized, context.data_dir):
            acc_paths = self._existing_paths(self._image_paths(city_img_path, self.ACCIDENT_IMAGES))
            if acc_paths:
                sections.append(self._render_image_section("Section 7: Accident Analysis", acc_paths))
            sumup_paths = self._existing_paths(self._image_paths(city_img_path, self.SUMUP_IMAGES[::-1]))
            if sumup_paths:
                sections.append(self._render_image_section("Section 8: Sum-Up Analysis", sumup_paths))

        return "\n".join(sections)
