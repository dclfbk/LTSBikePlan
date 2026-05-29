from __future__ import annotations

import os

import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox

from .common import city_output_dir, load_graph, save_placeholder


def run_gap_analysis(data_dir: str, images_dir: str, city: str) -> None:
    out_dir = city_output_dir(images_dir, city)
    graph = load_graph(data_dir, city)
    undirected = nx.Graph(graph)

    low_nodes = [n for n, d in undirected.nodes(data=True) if str(d.get("lts", "0")) in {"1", "2"}]
    low_sub = undirected.subgraph(low_nodes).copy()
    components = sorted(nx.connected_components(low_sub), key=len, reverse=True)

    comp_sizes = [len(c) for c in components[:10]] if components else [0]
    plt.figure(figsize=(8, 4))
    plt.bar(range(1, len(comp_sizes) + 1), comp_sizes, color="#4c78a8")
    plt.title("Top Connected Components")
    plt.xlabel("Component rank")
    plt.ylabel("Nodes")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "Top10connectedcomponents_plot.png"), dpi=200)
    plt.close()

    fig, ax = ox.plot_graph(graph, node_size=0, edge_linewidth=0.6, show=False, close=False)
    fig.savefig(os.path.join(out_dir, "highlowstresscomponents_plot.png"), dpi=200)
    plt.close(fig)

    # Simple proxy for "gaps"
    gap_count = max(0, len(components) - 1)
    plt.figure(figsize=(6, 4))
    plt.bar(["gaps"], [gap_count], color="#f58518")
    plt.title("Estimated Gaps")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "gaps_plot.png"), dpi=200)
    plt.close()

    save_placeholder(os.path.join(out_dir, "contact_nodes_plot.png"), "Contact nodes map placeholder")
    save_placeholder(os.path.join(out_dir, "heter_gapclosure_benefits.png"), "Gap closure heterogeneity placeholder")

    html_path = os.path.join(out_dir, "gaps_classified_plot.html")
    with open(html_path, "w") as file_handle:
        file_handle.write("<html><body><h3>Gap classification placeholder</h3></body></html>")
