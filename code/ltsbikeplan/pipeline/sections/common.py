from __future__ import annotations

import os

import matplotlib.pyplot as plt
import osmnx as ox


def city_output_dir(images_dir: str, area_slug: str) -> str:
    path = os.path.join(images_dir, area_slug)
    os.makedirs(path, exist_ok=True)
    return path


def load_graph(data_dir: str, area_slug: str):
    return ox.load_graphml(os.path.join(data_dir, area_slug, f"{area_slug}_lts.graphml"))


def save_placeholder(path: str, title: str) -> None:
    plt.figure(figsize=(8, 4))
    plt.text(0.5, 0.5, title, ha="center", va="center", fontsize=12)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
