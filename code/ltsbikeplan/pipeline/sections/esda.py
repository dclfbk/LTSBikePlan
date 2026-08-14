from __future__ import annotations

import os

import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox

from .common import city_output_dir, load_graph


def run_esda(data_dir: str, images_dir: str, area_slug: str) -> None:
    out_dir = city_output_dir(images_dir, area_slug)
    graph = load_graph(data_dir, area_slug)

    fig, ax = ox.plot_graph(graph, node_size=0, edge_linewidth=0.5, show=False, close=False)
    fig.savefig(os.path.join(out_dir, "network_base.png"), dpi=200)
    plt.close(fig)

    bearings = []
    for _, _, _, data in graph.edges(keys=True, data=True):
        b = data.get("bearing")
        if isinstance(b, (int, float)):
            bearings.append(float(b))
    if not bearings:
        bearings = [0.0]

    plt.figure(figsize=(8, 4))
    plt.hist(bearings, bins=36, color="#1f77b4", edgecolor="white")
    plt.title("Street Network Orientation")
    plt.xlabel("Bearing (degrees)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "streetnetworkorientation_plot.png"), dpi=200)
    plt.close()

    angles = np.deg2rad(np.array(bearings))
    plt.figure(figsize=(6, 6))
    ax = plt.subplot(111, projection="polar")
    ax.hist(angles, bins=36, color="#2ca02c", alpha=0.8)
    ax.set_title("Street Orientation Polar Plot")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "sno_polar_plot.png"), dpi=200)
    plt.close()
