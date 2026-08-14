from __future__ import annotations

import networkx as nx
import pandas as pd

_CENTRALITY_LABELS = ["low", "medium", "high", "very_high"]


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

    Sampled (k=250, matching pipeline/sections/network_analysis.py's node
    centrality), not exact - exact betweenness on a comune-sized graph is
    impractically slow in pure Python (~3h extrapolated for Trento vs ~33s
    sampled, measured).
    """
    all_lts = all_lts.copy()
    graph = nx.Graph()
    for (u, v, _key), length in zip(all_lts.index, all_lts["length"]):
        weight = float(length) if pd.notna(length) else 1.0
        graph.add_edge(u, v, length=weight)

    k = min(250, max(10, graph.number_of_nodes() // 10), graph.number_of_nodes())
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
