from __future__ import annotations

from typing import List, Optional

import networkx as nx
import numpy as np
import pandas as pd

from ltsbikeplan.domain.crs import chunked_to_crs

LOW_STRESS_LTS = {1, 2}
HIGH_STRESS_LTS = {3, 4}


def annotate_gap_components(
    all_lts: pd.DataFrame,
    area_slug: str,
    min_island_length_km: Optional[float] = None,
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

    return all_lts


def summarize_gap_components(all_lts, area_slug: str) -> list:
    """Per-component stats for the web viewer's gap panel: how big each
    low-stress island is and where to fly the map to look at it.

    Needs `all_lts` to already be a real GeoDataFrame with a CRS set (called
    after compute_lts.py's WORKING_CRS reprojection, unlike
    annotate_gap_components which only needs the index + `lts` column and
    runs before that reprojection).
    """
    islands = all_lts[all_lts["gap_component"].notna()]
    if islands.empty:
        return []

    islands_4326 = chunked_to_crs(islands, 4326)
    summary = []
    for comp_id, comp_edges in islands.groupby("gap_component"):
        bounds = islands_4326.loc[comp_edges.index].total_bounds
        summary.append(
            {
                "id": comp_id,
                "area": area_slug,
                "edge_count": int(len(comp_edges)),
                "length_km": round(float(comp_edges["length"].sum()) / 1000.0, 2),
                "bbox": [round(float(b), 6) for b in bounds],
            }
        )
    summary.sort(key=lambda c: c["length_km"], reverse=True)
    return summary
