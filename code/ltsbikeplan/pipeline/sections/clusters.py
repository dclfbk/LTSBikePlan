from __future__ import annotations

import os

import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import DBSCAN, OPTICS

from .common import city_output_dir, load_graph, save_placeholder


def _high_stress_points(graph):
    pts = []
    for _, data in graph.nodes(data=True):
        lts = data.get("lts")
        try:
            if int(lts) >= 4:
                pts.append((float(data["x"]), float(data["y"])))
        except Exception:
            continue
    return np.array(pts) if pts else np.zeros((0, 2))


def _save_scatter(points, labels, path, title):
    plt.figure(figsize=(7, 6))
    if len(points) > 0:
        plt.scatter(points[:, 0], points[:, 1], c=labels, s=8, cmap="tab20", alpha=0.8)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def run_clusters(data_dir: str, images_dir: str, area_slug: str) -> None:
    out_dir = city_output_dir(images_dir, area_slug)
    graph = load_graph(data_dir, area_slug)
    points = _high_stress_points(graph)

    if len(points) < 5:
        for name in [
            "dbscan_lts_cluster_geo.png",
            "dbscan_lts_cluster.png",
            "hdbscan_lts_cluster_geo.png",
            "hdbscan_lts_cluster.png",
            "optics_lts_cluster_geo.png",
            "optics_lts_cluster.png",
        ]:
            save_placeholder(os.path.join(out_dir, name), "Not enough high-stress points for clustering")
        return

    db_labels = DBSCAN(eps=0.001, min_samples=5).fit_predict(points)
    op_labels = OPTICS(min_samples=5).fit_predict(points)

    _save_scatter(points, db_labels, os.path.join(out_dir, "dbscan_lts_cluster.png"), "DBSCAN Clusters")
    _save_scatter(points, db_labels, os.path.join(out_dir, "dbscan_lts_cluster_geo.png"), "DBSCAN Clusters (Geo)")
    _save_scatter(points, op_labels, os.path.join(out_dir, "optics_lts_cluster.png"), "OPTICS Clusters")
    _save_scatter(points, op_labels, os.path.join(out_dir, "optics_lts_cluster_geo.png"), "OPTICS Clusters (Geo)")

    _save_scatter(points, db_labels, os.path.join(out_dir, "hdbscan_lts_cluster.png"), "HDBSCAN-style Clusters")
    _save_scatter(points, db_labels, os.path.join(out_dir, "hdbscan_lts_cluster_geo.png"), "HDBSCAN-style Clusters (Geo)")
