import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    import osmnx as ox
    import pandas as pd
    from shapely.geometry import LineString, Point

    from ltsbikeplan.services.graph_services import GraphLoaderService, UrbanContextClassifier

    GEO_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - geo deps optional in this env
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/osmnx (geo extras) not installed")
class TestFilterMajorRoads(unittest.TestCase):
    def test_trunk_footway_path_and_service_are_kept(self):
        # All four used to be silently dropped here, before the network
        # ever reached BikePathAnalysis - they'd vanish from the graph
        # entirely instead of being classified (trunk: high-LTS or "not
        # allowed"; footway/path: separated-path rules incl. the s9
        # mountain-trail check; service: mixed_traffic's alley/driveway/
        # parking_aisle rules). Confirmed empirically: a live Trento run
        # produced zero s1/s2/s9 edges before this fix.
        gdf_edges = gpd.GeoDataFrame(
            {"highway": ["trunk", "trunk_link", "footway", "path", "service", "razed"]},
            geometry=[LineString([(0, 0), (1, 1)])] * 6,
            crs="EPSG:4326",
        )
        filtered = GraphLoaderService().filter_major_roads(gdf_edges)
        self.assertListEqual(
            sorted(filtered["highway"]),
            ["footway", "path", "service", "trunk", "trunk_link"],
        )


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/osmnx (geo extras) not installed")
class TestDownloadGraphFetchesExtraTags(unittest.TestCase):
    def test_extra_tags_are_added_to_useful_tags_way(self):
        # osmnx doesn't fetch "motorroad"/"sac_scale"/"mtb:scale" by
        # default - without this, the rules in BikePathAnalysis that read
        # them (trunk/motorroad legal restriction, mountain-trail
        # difficulty) would never see the tags on the osmnx ingestion path.
        original_tags = list(ox.settings.useful_tags_way)
        ox.settings.useful_tags_way = [
            tag for tag in original_tags if tag not in {"motorroad", "sac_scale", "mtb:scale"}
        ]
        try:
            with mock.patch("ltsbikeplan.services.graph_services.ox.graph_from_place") as mock_graph_from_place, \
                 mock.patch("ltsbikeplan.services.graph_services.ox.graph_to_gdfs") as mock_graph_to_gdfs:
                mock_graph_to_gdfs.return_value = (gpd.GeoDataFrame(), gpd.GeoDataFrame())
                GraphLoaderService().download_graph("Test City")
            for tag in ("motorroad", "sac_scale", "mtb:scale"):
                self.assertIn(tag, ox.settings.useful_tags_way)
        finally:
            ox.settings.useful_tags_way = original_tags


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/osmnx (geo extras) not installed")
class TestClassifyEdgesByQuintiles(unittest.TestCase):
    def test_edge_near_a_building_is_urban_others_stay_countryside(self):
        # Was previously a gpd.sjoin() call per edge in a Python loop -
        # ~150x slower than the single vectorized sjoin this replaced it
        # with (29s -> 0.2s on a synthetic 3000-edge/3000-building
        # benchmark), very plausibly the dominant per-comune cost given
        # this runs once per area's full edge set during fetch. Confirms
        # the vectorized version keeps the exact same "any building within
        # urban_threshold of the edge centroid" semantics.
        edges = gpd.GeoDataFrame(
            geometry=[
                LineString([(0, 0), (0, 0.001)]),  # centroid near the building below - urban
                LineString([(10, 10), (10, 10.001)]),  # far from any building - countryside
            ],
            crs="EPSG:4326",
        )
        buildings = gpd.GeoDataFrame(geometry=[Point(0, 0.0005)], crs="EPSG:4326")
        # quintiles[2] is the urban_threshold this method reads - values
        # in metres once reprojected to the edges' own estimated UTM CRS.
        quintiles = [0, 0, 200, 0, 0]

        result = UrbanContextClassifier().classify_edges_by_quintiles(edges, buildings, quintiles)

        self.assertListEqual(list(result["context"]), ["urban", "countryside"])

    def test_preserves_a_multiindex_like_osmnx_edges(self):
        # osmnx edges carry a (u, v, key) MultiIndex, not a plain
        # RangeIndex - the vectorized rewrite builds an intermediate
        # GeoDataFrame keyed by edge position internally, which broke on a
        # MultiIndex input during development ("incompatible index of
        # inserted column with frame index") until geometry was passed as
        # .values instead of the geometry Series (which still carried the
        # original MultiIndex, misaligned against the intermediate frame's
        # own fresh RangeIndex).
        idx = pd.MultiIndex.from_tuples([(1, 2, 0), (3, 4, 0)], names=["u", "v", "key"])
        edges = gpd.GeoDataFrame(
            geometry=[LineString([(0, 0), (0, 0.001)]), LineString([(10, 10), (10, 10.001)])],
            index=idx,
            crs="EPSG:4326",
        )
        buildings = gpd.GeoDataFrame(geometry=[Point(0, 0.0005)], crs="EPSG:4326")
        quintiles = [0, 0, 200, 0, 0]

        result = UrbanContextClassifier().classify_edges_by_quintiles(edges, buildings, quintiles)

        self.assertIsInstance(result.index, pd.MultiIndex)
        self.assertListEqual(list(result.index), [(1, 2, 0), (3, 4, 0)])
        self.assertListEqual(list(result["context"]), ["urban", "countryside"])


if __name__ == "__main__":
    unittest.main()
