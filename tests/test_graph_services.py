import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    import osmnx as ox
    from shapely.geometry import LineString

    from ltsbikeplan.services.graph_services import GraphLoaderService

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


if __name__ == "__main__":
    unittest.main()
