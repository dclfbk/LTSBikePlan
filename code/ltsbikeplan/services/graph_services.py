from __future__ import annotations

import os

import numpy as np
import geopandas as gpd
import osmnx as ox
from sklearn.neighbors import NearestNeighbors

from ltsbikeplan.domain.crs import WORKING_CRS, chunked_to_crs

# osmnx's default Overpass endpoint (overpass-api.de) has no failover to
# any of the other public community mirrors when it's down/refusing
# connections - confirmed 2026-09-04 (ConnectionRefusedError while
# reprocessing the Friuli backlog via LTSBP_NO_OSMIT_ESTRATTI=1). Set this
# to switch mirrors (e.g. "https://overpass.private.coffee/api" - base
# URL, no trailing "/interpreter": osmnx's own _overpass.py appends that
# itself - verified reachable that day when overpass-api.de and
# overpass.kumi.systems both weren't) without touching code. The setting
# is named overpass_url, not overpass_endpoint, in this osmnx version
# (2.1.0) - ox.settings otherwise silently accepts and ignores any
# attribute name, so a typo here fails silent, not loud.
_OVERPASS_URL = os.environ.get("LTSBP_OVERPASS_URL")
if _OVERPASS_URL:
    ox.settings.overpass_url = _OVERPASS_URL
    # osmnx paces itself by polling the endpoint's own /status page and
    # parsing a specific line of it (_overpass._get_overpass_pause) to
    # decide how long to wait for a free slot - written against
    # overpass-api.de's exact status format. maps.mail.ru's /status has a
    # differently-shaped line in that same position ("Rate limit: 0"
    # where overpass-api.de has a numeric "N slots available" line),
    # which osmnx's parser reads as "a query is currently running" and
    # recurses every 5s to recheck - forever, since that line never
    # changes. Reproduced 2026-09-04: an 8+ minute hang on Ampezzo with
    # zero output, not a slow query - the graph_from_place call never
    # even reached Overpass. Disabling the whole rate-limit dance instead
    # of trying to keep it working across mirrors with different status
    # formats.
    ox.settings.overpass_rate_limit = False

# Tags BikePathAnalysis reads that aren't in osmnx's default
# useful_tags_way - without these, they'd silently never reach the domain
# rules that need them on the osmnx ingestion path (motorroad: trunk/
# trunk_link legally barred to bicycles; sac_scale: mountain trails too
# technical for a city/e-bike despite being highway=path/footway;
# zone:maxspeed: Italian "Zona 30" traffic-calmed zones are frequently
# tagged only with zone:maxspeed=IT:30, no plain maxspeed at all - without
# this, get_max_speed's fallback chain never sees it and assumes a bare
# 50 km/h `local` default instead, understating how calm the street
# actually is). mtb:scale was here too at one point - dropped along with
# the domain rule that read it, see lts_rules.py's _HARD_SAC_SCALE_VALUES
# comment for why.
_EXTRA_USEFUL_TAGS_WAY = ["motorroad", "sac_scale", "zone:maxspeed"]


class GraphLoaderService:
    def _ensure_extra_tags(self) -> None:
        missing_tags = [tag for tag in _EXTRA_USEFUL_TAGS_WAY if tag not in ox.settings.useful_tags_way]
        if missing_tags:
            ox.settings.useful_tags_way = ox.settings.useful_tags_way + missing_tags

    def download_graph(self, city: str):
        self._ensure_extra_tags()
        graph = ox.graph_from_place(city, network_type="all")
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(graph)
        return graph, gdf_nodes, gdf_edges

    def download_graph_from_polygon(self, polygon):
        """Same as download_graph, but bypasses Nominatim place-name
        resolution entirely - for the rare comune with no administrative
        boundary relation in OSM at all (see AreaSpec.boundary_geojson),
        where graph_from_place has nothing to resolve the name to."""
        self._ensure_extra_tags()
        graph = ox.graph_from_polygon(polygon, network_type="all")
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(graph)
        return graph, gdf_nodes, gdf_edges

    def filter_major_roads(self, gdf_edges):
        major_roads = [
            "primary",
            "primary_link",
            "secondary",
            "secondary_link",
            "tertiary",
            "tertiary_link",
            "residential",
            "cycleway",
            "living_street",
            "unclassified",
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "pedestrian",
            "steps",
            "track",
            # footway/path/service used to be missing here, silently
            # dropping them before BikePathAnalysis ever saw them even
            # though the rest of the pipeline clearly expects them
            # (EXTRA_NETWORK_ATTRIBUTES fetches their tags, lts_rules.py
            # has dedicated rules for all three - is_separated_path's
            # s1/s2/s9 for footway/path, mixed_traffic's m2/m3/m4/m16 for
            # service). Confirmed empirically: a live Trento run produced
            # zero s1/s2/s9 edges before this fix.
            "footway",
            "path",
            "service",
        ]
        return gdf_edges[gdf_edges["highway"].isin(major_roads)]

    def fetch_building_data(self, city: str):
        print(f"Fetching building data for {city}...")
        buildings = ox.features_from_place(city, tags={"building": True})
        print(f"Number of buildings fetched: {len(buildings)}")
        return buildings

    def fetch_building_data_from_polygon(self, polygon, name: str):
        print(f"Fetching building data for {name}...")
        buildings = ox.features_from_polygon(polygon, tags={"building": True})
        print(f"Number of buildings fetched: {len(buildings)}")
        return buildings


class UrbanContextClassifier:
    def calculate_building_distances(self, gdf_buildings):
        print(f"Calculating distances for {len(gdf_buildings)} buildings...")
        gdf_projected = gdf_buildings.to_crs(gdf_buildings.estimate_utm_crs() or WORKING_CRS)
        building_coords = np.array(list(gdf_projected.geometry.centroid.apply(lambda x: (x.x, x.y))))
        nbrs = NearestNeighbors(n_neighbors=2, algorithm="ball_tree").fit(building_coords)
        distances, _ = nbrs.kneighbors(building_coords)
        return distances[:, 1]

    def divide_into_quintiles(self, distances):
        return np.percentile(distances, [20, 40, 60, 80, 100])

    def classify_edges_by_quintiles(self, gdf_edges, gdf_buildings, quintiles):
        urban_threshold = quintiles[2]
        print(f"Urban threshold set at {urban_threshold} units")
        gdf_edges = gdf_edges.copy()
        gdf_edges["context"] = "countryside"
        target_crs = gdf_edges.estimate_utm_crs() or gdf_edges.crs
        gdf_edges = chunked_to_crs(gdf_edges, target_crs)
        gdf_buildings = gdf_buildings.to_crs(target_crs)

        # One spatial join for every edge at once, instead of a Python loop
        # running a fresh gpd.sjoin() per edge (each rebuilding a spatial
        # index over gdf_buildings from scratch) - same "any building
        # within urban_threshold of the edge centroid" test, ~150x faster
        # on a synthetic 3000-edge/3000-building benchmark (29s -> 0.2s,
        # verified identical output). This step runs on every area's full
        # edge set during fetch, so at real comune scale (tens of
        # thousands of edges) it was very plausibly the single biggest
        # contributor to per-comune processing time.
        # .values strips the geometry Series' own index before handing it to
        # the constructor - gdf_edges.index (e.g. osmnx's (u, v, key)
        # MultiIndex) doesn't line up with the fresh default RangeIndex a
        # dict-built GeoDataFrame gets otherwise, which pandas refuses to
        # reconcile ("incompatible index of inserted column with frame
        # index"). Positional values line up correctly either way.
        buffers = gpd.GeoDataFrame(
            {"edge_index": gdf_edges.index},
            geometry=gdf_edges.geometry.centroid.buffer(urban_threshold).values,
            crs=gdf_edges.crs,
        )
        joined = gpd.sjoin(buffers, gdf_buildings[["geometry"]], how="inner", predicate="intersects")
        urban_edge_indices = joined["edge_index"].unique()
        gdf_edges.loc[urban_edge_indices, "context"] = "urban"

        return gdf_edges
