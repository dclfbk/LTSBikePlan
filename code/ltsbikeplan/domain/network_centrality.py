from __future__ import annotations

import networkx as nx
import pandas as pd

_CENTRALITY_LABELS = ["low", "medium", "high", "very_high"]

# Trento comune, measured on this machine: 143,828 edges, k=250 -> ~117s.
# Used below as the reference point for scaling k down on bigger graphs.
_REFERENCE_EDGES = 144_000
_REFERENCE_K = 250
_MIN_K_LARGE_GRAPH = 25


def _build_graph(all_lts: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for (u, v, _key), length in zip(all_lts.index, all_lts["length"]):
        weight = float(length) if pd.notna(length) else 1.0
        graph.add_edge(u, v, length=weight)
    return graph


def annotate_edge_centrality(all_lts: pd.DataFrame) -> pd.DataFrame:
    """Tags every edge with its betweenness centrality in the area's full
    road network (not just the low-stress subgraph) - how many shortest
    paths are forced through it. High centrality + high LTS is what makes a
    stressful street an actual priority, not just an uncomfortable one.

    Builds the graph directly from `all_lts`'s own (u, v, key) index and
    `length` column, same convention as domain/gap_analysis.py's subgraph
    construction - no dependency on the osmnx MultiDiGraph object built
    later in compute_lts.py for the GraphML export (which round-trips
    through a stringifying XML step not needed here).

    Sampled (k up to 250, matching pipeline/sections/network_analysis.py's
    node centrality), not exact - exact betweenness on a comune-sized graph
    is impractically slow in pure Python (~3h extrapolated for Trento vs
    ~117s sampled, measured).

    k adapts to graph size two ways: the existing small-graph floor (fewer
    nodes -> fewer samples needed - unchanged below) and, past
    _REFERENCE_EDGES, a large-graph ceiling that shrinks k so total
    sampling work (k * edges) stays close to what the comune-sized
    reference graph costs. Without the second part, k stayed flat at 250
    regardless of graph size, so a provincia-sized graph (dozens of comuni,
    many times more edges) took tens of minutes to hours just for this step.
    A smaller k on a huge graph means noisier centrality estimates, not
    wrong ones - Brandes' sampling error bound depends on k in absolute
    terms, not as a fraction of graph size, so this trades precision for
    time on big areas rather than breaking correctness.
    """
    all_lts = all_lts.copy()
    graph = _build_graph(all_lts)

    k = min(250, max(10, graph.number_of_nodes() // 10), graph.number_of_nodes())
    if graph.number_of_edges() > _REFERENCE_EDGES:
        k = min(k, max(_MIN_K_LARGE_GRAPH, round(_REFERENCE_K * _REFERENCE_EDGES / graph.number_of_edges())))
    raw = nx.edge_betweenness_centrality(graph, k=k, weight="length", seed=42)
    lookup = {frozenset(edge): value for edge, value in raw.items()}

    all_lts["centrality"] = [lookup.get(frozenset((u, v)), 0.0) for u, v, _key in all_lts.index]
    all_lts["centrality_class"] = _bucket_centrality(all_lts["centrality"])
    return all_lts


def _bucket_centrality(values: pd.Series) -> pd.Series:
    """Quantile buckets within THIS area's own distribution - raw
    betweenness isn't comparable across differently-sized road networks.
    Exact zero ("never on a sampled shortest path") is pulled out as its
    own bucket before qcut-ing the remainder: real betweenness on street
    networks is often zero-heavy on residential dead-ends (7.8% measured on
    Trento, could be much higher on small/rural areas), which can make a
    plain 4-way qcut raise (duplicate bin edges) or silently collapse into
    a lopsided bottom bin via duplicates="drop".
    """
    result = pd.Series("zero", index=values.index, dtype=object)
    nonzero = values[values > 0]
    if nonzero.empty:
        return result
    bins = pd.qcut(nonzero, q=4, duplicates="drop")
    codes = bins.cat.codes
    labels = _CENTRALITY_LABELS[-(codes.max() + 1):]
    result.loc[nonzero.index] = [labels[c] for c in codes]
    return result


def annotate_dead_end_branches(all_lts: pd.DataFrame) -> pd.DataFrame:
    """Tags every BRIDGE edge (one whose removal disconnects the graph)
    with `served_branch_km`: the total street length of the SMALLER side it
    would cut off - a proxy for "how much does this edge actually serve".
    domain/gap_analysis.py uses it to stop flagging a residential
    cul-de-sac's own connector edge as a priority intervention just because
    it's high-stress and happens to touch a low-stress area: a single stem
    feeding a 300m dead-end loop of a dozen houses isn't a "mandatory
    passage many trips are forced through" (the framing annotate_edge_
    centrality's betweenness is meant to capture) - it's a mandatory
    passage for THOSE houses only, which raw topological betweenness can't
    tell apart from a real through-route once quantile-bucketed within a
    small/rural area's mostly-zero distribution (see _bucket_centrality).

    Non-bridge edges (anywhere with an alternate route - almost every edge
    in a normal street network, since a real network is full of loops) get
    NaN here: "not a bottleneck for anything," not "serves zero km."

    Computed via the bridge tree, not by removing and re-measuring each
    bridge individually (O(bridges * V), impractically slow on a comune
    with hundreds of dead-end streets): every bridge-free maximal subgraph
    ("block") is contracted to one node; connecting blocks by their bridges
    always yields a tree (a forest, if the input itself has more than one
    connected component) - one post-order pass over it gives every
    bridge's smaller-side length in a single O(V+E) sweep.
    """
    all_lts = all_lts.copy()
    graph = _build_graph(all_lts)
    bridge_edges = {frozenset(e) for e in nx.bridges(graph)}

    block_graph = graph.copy()
    block_graph.remove_edges_from(tuple(e) for e in bridge_edges)
    node_to_block = {}
    block_km = {}
    for block_id, nodes in enumerate(nx.connected_components(block_graph)):
        for node in nodes:
            node_to_block[node] = block_id
        block_km[block_id] = block_graph.subgraph(nodes).size(weight="length") / 1000.0

    # Bridge tree: one node per block, one edge per bridge (guaranteed to
    # connect two DIFFERENT blocks - that's what makes it a bridge).
    tree = nx.Graph()
    tree.add_nodes_from(block_km)
    bridge_by_tree_edge = {}
    for u, v, data in graph.edges(data=True):
        if frozenset((u, v)) not in bridge_edges:
            continue
        block_u, block_v = node_to_block[u], node_to_block[v]
        tree.add_edge(block_u, block_v, length=data["length"])
        bridge_by_tree_edge[frozenset((block_u, block_v))] = frozenset((u, v))

    smaller_side_km = {}  # original-graph bridge (frozenset of nodes) -> km
    for component in nx.connected_components(tree):
        root = next(iter(component))
        post_order = list(nx.dfs_postorder_nodes(tree, source=root))
        parent_of = dict(nx.bfs_predecessors(tree, source=root))
        subtree_km = {}
        for node in post_order:
            total = block_km.get(node, 0.0)
            for neighbor in tree.neighbors(node):
                if parent_of.get(neighbor) == node:
                    total += subtree_km[neighbor] + tree[node][neighbor]["length"] / 1000.0
            subtree_km[node] = total
        total_km = subtree_km[root]

        for child, parent in parent_of.items():
            child_side_km = subtree_km[child]
            edge_km = tree[parent][child]["length"] / 1000.0
            other_side_km = total_km - child_side_km - edge_km
            original_edge = bridge_by_tree_edge[frozenset((parent, child))]
            smaller_side_km[original_edge] = min(child_side_km, other_side_km)

    all_lts["served_branch_km"] = [
        smaller_side_km.get(frozenset((u, v))) for u, v, _key in all_lts.index
    ]
    return all_lts
