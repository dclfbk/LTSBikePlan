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
# treating genuinely interior components as boundary-adjacent.
BOUNDARY_TOUCH_BUFFER_M = 100.0


def drop_isolated_interior_components(
    gdf_nodes: gpd.GeoDataFrame,
    gdf_edges: gpd.GeoDataFrame,
    boundary_polygon,
    min_length_km: float = MIN_COMPONENT_LENGTH_KM,
    boundary_buffer_m: float = BOUNDARY_TOUCH_BUFFER_M,
) -> gpd.GeoDataFrame:
    """Drops edges belonging to a short connected component of the road/
    path network that doesn't touch the comune's own administrative
    boundary - a real, disconnected fragment (e.g. an unconnected network
    of paths inside a park, confirmed as a real recurring nuisance on the
    live map) rather than a road merely cut short by the comune extract's
    own edge, which - per ROUTING.md's own note on shared, un-renumbered
    OSM node ids across adjacent comuni extracts - keeps flowing into the
    neighbouring comune's own extract in reality and must NOT be dropped
    just because it looks like a dead end from inside this one extract
    alone.

    `boundary_polygon` (shapely (Multi)Polygon, EPSG:4326) should come from
    AreaResolver.get_comune_boundary_polygon - if None (18 known comuni
    with no decodable boundary geometry in osmit-estratti's topojson, an
    area resolved some other way, or simply offline), this is a no-op:
    every component is kept, matching this project's existing default
    (osm_pbf_service.py's retain_all=True) of never silently dropping a
    real island of the road network when there's any doubt.

    `gdf_nodes`/`gdf_edges` are the shapes every ingestion path in this
    project already normalizes to (osmnx.graph_to_gdfs - node id-indexed
    points, (u, v, key)-indexed edges with a `length` column in metres).
    Operates on the FULL network (every highway class, not just the
    bikeable subset) since real connectivity can run through any road
    type - filtering only the bikeable edges first would make a fragment
    that's actually connected via a plain residential street look falsely
    isolated.
    """
    if boundary_polygon is None or getattr(boundary_polygon, "is_empty", True) or gdf_edges.empty:
        return gdf_edges

    graph = nx.Graph()
    graph.add_edges_from((u, v) for u, v, _ in gdf_edges.index)
    components = list(nx.connected_components(graph))
    if len(components) <= 1:
        return gdf_edges

    node_component = {node: i for i, comp in enumerate(components) for node in comp}

    us = gdf_edges.index.get_level_values(0)
    # Every edge's endpoints share one component by construction (the graph
    # above was built from these same edges) - only `u` is needed to look
    # up which component an edge belongs to.
    comp_ids = pd.Series([node_component[u] for u in us], index=gdf_edges.index)
    comp_length_km = (gdf_edges["length"] / 1000.0).groupby(comp_ids).sum()
    small_components = set(comp_length_km[comp_length_km < min_length_km].index)
    if not small_components:
        return gdf_edges

    small_component_node_ids = [node for node, cid in node_component.items() if cid in small_components]
    candidate_node_ids = [node_id for node_id in small_component_node_ids if node_id in gdf_nodes.index]
    if not candidate_node_ids:
        return gdf_edges

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
        return gdf_edges

    return gdf_edges[~comp_ids.isin(components_to_drop)]
