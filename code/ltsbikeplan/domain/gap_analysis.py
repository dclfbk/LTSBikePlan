from __future__ import annotations

from typing import List, Optional

import networkx as nx
import numpy as np
import pandas as pd


LOW_STRESS_LTS = {1, 2}
HIGH_STRESS_LTS = {3, 4}


def annotate_gap_components(
    all_lts: pd.DataFrame,
    area_slug: str,
    min_island_length_km: Optional[float] = None,
    min_branch_length_km: Optional[float] = None,
) -> pd.DataFrame:
    """Tags every edge with the low-stress "island" (connected component) it
    belongs to, and flags high-stress edges that touch one - the literal
    candidates for "improve this segment to close a gap".

    `pipeline/sections/gap_analysis.py`'s existing component search filters
    NODES by their own LTS (the max over incident edges), which excludes
    exactly the boundary nodes this needs: a node with one low-stress and
    one high-stress edge gets the high-stress node LTS and would be dropped.
    Building the subgraph from low-stress EDGES directly keeps a boundary
    node reachable from its low-stress side.

    `all_lts` must be indexed by (u, v, key) as produced by
    osmnx.graph_to_gdfs (the shape every ingestion path in this project
    already normalizes to - see services/osm_pbf_service.py). Only the
    index and the `lts` column are read (plus `length` if
    `min_island_length_km` is set); no geometry/CRS needed here.

    `min_island_length_km`, if set, downgrades `is_gap_edge` back to False
    for edges that only touch islands smaller than this - without it, a
    2-edge residential loop in an isolated hamlet competes equally with a
    15km urban low-stress network for a planner's attention. Defaults to
    None (off) so callers that only ever provide an `lts` column (no
    `length`, e.g. this module's own unit tests) keep working unchanged.

    `min_branch_length_km`, if set, downgrades `is_gap_edge` back to False
    for edges whose own `served_branch_km` (domain/network_centrality.py's
    annotate_dead_end_branches - the total street length on the smaller
    side of a bridge edge) is below this threshold: a residential
    cul-de-sac's own connector edge is high-stress and touches a low-stress
    island just like a real through-route would, but it isn't a priority
    intervention if all it serves is a handful of houses at a dead end.
    Requires `served_branch_km` to already be a column on `all_lts` (call
    annotate_dead_end_branches first) - silently skipped (no downgrade) if
    the column is missing, same "off by default" convention as
    min_island_length_km.
    """
    all_lts = all_lts.copy()
    low_stress_mask = all_lts["lts"].isin(LOW_STRESS_LTS)

    graph = nx.Graph()
    graph.add_edges_from((u, v) for u, v, _ in all_lts.index[low_stress_mask.to_numpy()])
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    node_to_component = {node: f"{area_slug}:{i}" for i, comp in enumerate(components) for node in comp}

    us = all_lts.index.get_level_values(0)
    vs = all_lts.index.get_level_values(1)
    comp_u = [node_to_component.get(u) for u in us]
    comp_v = [node_to_component.get(v) for v in vs]

    gap_component: List[Optional[str]] = []
    is_gap_edge: List[bool] = []
    gap_connects: List[Optional[str]] = []
    high_stress = all_lts["lts"].isin(HIGH_STRESS_LTS).to_numpy()

    for low, high, cu, cv in zip(low_stress_mask.to_numpy(), high_stress, comp_u, comp_v):
        if low:
            # cu == cv here: both endpoints of a low-stress edge are
            # necessarily in the same component (this edge connects them).
            gap_component.append(cu if cu is not None else cv)
            is_gap_edge.append(False)
            gap_connects.append(np.nan)
            continue

        touched = sorted({c for c in (cu, cv) if c is not None})
        gap_component.append(np.nan)
        if high and touched:
            is_gap_edge.append(True)
            gap_connects.append(",".join(touched))
        else:
            is_gap_edge.append(False)
            gap_connects.append(np.nan)

    all_lts["gap_component"] = gap_component
    all_lts["is_gap_edge"] = is_gap_edge
    all_lts["gap_connects"] = gap_connects

    if min_island_length_km is not None:
        island_length_km = all_lts.loc[low_stress_mask].groupby("gap_component")["length"].sum() / 1000.0
        too_small = set(island_length_km[island_length_km < min_island_length_km].index)

        def _touches_only_small_islands(connects):
            return not pd.isna(connects) and all(cid in too_small for cid in connects.split(","))

        # An edge touching ANY sufficiently large island keeps is_gap_edge -
        # still worth flagging even if its other end touches a tiny one.
        downgrade = all_lts["is_gap_edge"] & all_lts["gap_connects"].apply(_touches_only_small_islands)
        all_lts.loc[downgrade, "is_gap_edge"] = False
        all_lts.loc[downgrade, "gap_connects"] = np.nan

    if min_branch_length_km is not None and "served_branch_km" in all_lts.columns:
        # served_branch_km is NaN for a non-bridge edge (has an alternate
        # route - not "this edge serves nothing", the opposite: it isn't a
        # bottleneck for anything, so it's never downgraded by this check).
        branch_too_small = all_lts["served_branch_km"] < min_branch_length_km
        downgrade = all_lts["is_gap_edge"] & branch_too_small
        all_lts.loc[downgrade, "is_gap_edge"] = False
        all_lts.loc[downgrade, "gap_connects"] = np.nan

    return all_lts
