from __future__ import annotations

import geopandas as gpd
import networkx as nx
import pandas as pd

from ltsbikeplan.domain.crs import WORKING_CRS, chunked_to_crs

# Below this total length, a connected component is a candidate for
# dropping - same order of magnitude as MIN_RELIABLE_SLOPE_LENGTH_M
# (lts_rules.py) and MIN_GAP_BRANCH_LENGTH_KM (compute_lts.py): short
# enough that it's very unlikely to be a real, useful standalone route
# (a genuine isolated hamlet's own road network, say) rather than either a
# small mapping artifact or an unconnected park path loop.
MIN_COMPONENT_LENGTH_KM = 0.5

# How close a component's node has to be to the comune's own boundary line
# to count as "probably continues into the neighbouring comune's extract"
# rather than a genuine interior dead end - generous enough to survive
# boundary-polygon imprecision (osmit-estratti's topojson simplification,
# real-world GPS/digitisation noise) without being so wide it starts
# treating genuinely interior components as boundary-adjacent. Was 100m
# until a real case (OSM way 594202617, a hillside path in Arenzano)
# proved that too generous: its component's closest node sat 95m from the
# comune boundary purely because the boundary line cuts across that
# hillside, not because the path actually continues anywhere - it was
# wrongly exempted from pruning. 50m still comfortably survives the
# topojson-simplification/GPS-noise case this buffer exists for, while no
# longer catching that false positive.
BOUNDARY_TOUCH_BUFFER_M = 50.0


def drop_isolated_bikeable_components(
    gdf_nodes: gpd.GeoDataFrame,
    all_lts: pd.DataFrame,
    boundary_polygon,
    min_length_km: float = MIN_COMPONENT_LENGTH_KM,
    boundary_buffer_m: float = BOUNDARY_TOUCH_BUFFER_M,
) -> pd.DataFrame:
    """Drops edges belonging to a short connected component of the
    BIKEABLE network (`lts` > 0) that doesn't touch the comune's own
    administrative boundary - a real, disconnected fragment (e.g. an
    unconnected network of paths inside a park, or a Venice-style knot of
    sottoporteghi only reachable from the rest of the city via unramped
    steps) rather than a road merely cut short by the comune extract's own
    edge, which - per ROUTING.md's own note on shared, un-renumbered OSM
    node ids across adjacent comuni extracts - keeps flowing into the
    neighbouring comune's own extract in reality and must NOT be dropped
    just because it looks like a dead end from inside this one extract
    alone.

    Connectivity is checked ONLY through other bikeable edges (`lts` > 0),
    not the raw physical network - an earlier version of this function
    used the full graph (every highway class, including excluded ones) on
    the theory that "a fragment connected via a plain residential street
    shouldn't look isolated just because that street wasn't counted." That
    reasoning doesn't hold: a residential street is itself bikeable, so it
    was ALREADY part of the bikeable subgraph - the full-graph version's
    real effect was instead to treat a fragment as "connected" through a
    link no cyclist can actually use (unramped steps, a mountain trail
    excluded for being too technical, a private-access road), which is
    exactly backwards for this feature's purpose. Confirmed on two real
    cases: OSM way 958785510 (a short pedestrian tunnel/sottoportego in
    central Venice) forms its own 5-node/45m bikeable-only island, only
    reachable from the rest of Venice's enormous physically-connected
    network via other pedestrian passages and unramped bridge steps; OSM
    way 594202617 (a hillside path in Arenzano) forms a 25-node/162m
    bikeable-only island for the same reason - both were WRONGLY kept by
    the full-graph version, since Venice's/Arenzano's full physical network
    (686km/4523km) is one single connected piece regardless of what a
    bicycle can actually ride on.

    `boundary_polygon` (shapely (Multi)Polygon, EPSG:4326) should come from
    AreaResolver.get_comune_boundary_polygon - if None (18 known comuni
    with no decodable boundary geometry in osmit-estratti's topojson, an
    area resolved some other way, or simply offline), this is a no-op:
    every component is kept, matching this project's existing default
    (osm_pbf_service.py's retain_all=True) of never silently dropping a
    real island of the road network when there's any doubt.

    `all_lts` is the pipeline's combined post-classification frame
    (compute_lts.py, (u, v, key)-indexed, `lts`/`length` columns already
    present) - called AFTER LTS classification, not before, since it needs
    to know which edges are actually bikeable. Only ever drops rows that
    were themselves bikeable (`lts` > 0); an excluded (`lts` == 0) edge
    dangling off a dropped island is left as-is; it was already hidden
    from the map by default.

    `gdf_nodes` is the shape every ingestion path in this project already
    normalizes to (osmnx.graph_to_gdfs - node id-indexed points).
    """
    if boundary_polygon is None or getattr(boundary_polygon, "is_empty", True) or all_lts.empty:
        return all_lts

    bikeable = all_lts[all_lts["lts"] > 0]
    if bikeable.empty:
        return all_lts

    graph = nx.Graph()
    graph.add_edges_from((u, v) for u, v, _ in bikeable.index)
    components = list(nx.connected_components(graph))
    if len(components) <= 1:
        return all_lts

    node_component = {node: i for i, comp in enumerate(components) for node in comp}

    us = bikeable.index.get_level_values(0)
    # Every edge's endpoints share one component by construction (the graph
    # above was built from these same edges) - only `u` is needed to look
    # up which component an edge belongs to.
    comp_ids = pd.Series([node_component[u] for u in us], index=bikeable.index)
    comp_length_km = (bikeable["length"] / 1000.0).groupby(comp_ids).sum()
    small_components = set(comp_length_km[comp_length_km < min_length_km].index)
    if not small_components:
        return all_lts

    small_component_node_ids = [node for node, cid in node_component.items() if cid in small_components]
    candidate_node_ids = [node_id for node_id in small_component_node_ids if node_id in gdf_nodes.index]
    if not candidate_node_ids:
        return all_lts

    boundary_gs = gpd.GeoSeries([boundary_polygon], crs="EPSG:4326")
    boundary_gs = chunked_to_crs(gpd.GeoDataFrame(geometry=boundary_gs), WORKING_CRS).geometry
    boundary_line = boundary_gs.iloc[0].boundary

    candidate_nodes = gdf_nodes.loc[candidate_node_ids]
    if candidate_nodes.crs is None:
        candidate_nodes = candidate_nodes.set_crs("EPSG:4326")
    candidate_nodes = chunked_to_crs(candidate_nodes, WORKING_CRS)
    touches_boundary = candidate_nodes.geometry.distance(boundary_line) <= boundary_buffer_m

    boundary_touching_components = {
        node_component[node_id] for node_id, touches in zip(candidate_node_ids, touches_boundary) if touches
    }
    components_to_drop = small_components - boundary_touching_components
    if not components_to_drop:
        return all_lts

    drop_index = comp_ids[comp_ids.isin(components_to_drop)].index
    return all_lts.drop(index=drop_index)
