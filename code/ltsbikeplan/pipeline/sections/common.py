from __future__ import annotations

import os

import matplotlib.pyplot as plt
import osmnx as ox

from ltsbikeplan.utils import sanitize_city_name


def city_output_dir(images_dir: str, city: str) -> str:
    path = os.path.join(images_dir, sanitize_city_name(city))
    os.makedirs(path, exist_ok=True)
    return path


def load_graph(data_dir: str, city: str):
    city_name = sanitize_city_name(city)
    return ox.load_graphml(os.path.join(data_dir, f"{city_name}_lts.graphml"))


def save_placeholder(path: str, title: str) -> None:
    plt.figure(figsize=(8, 4))
    plt.text(0.5, 0.5, title, ha="center", va="center", fontsize=12)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
