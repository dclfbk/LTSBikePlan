import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    from shapely.geometry import LineString
except ImportError:  # pragma: no cover - geo deps optional in this env
    gpd = None

from ltsbikeplan.domain.area_spec import AreaSpec


@unittest.skipUnless(gpd is not None, "geopandas/shapely not installed")
class TestLoadNetworkOsmnxBbox(unittest.TestCase):
    def test_osmnx_branch_computes_bbox_from_downloaded_edges(self):
        from ltsbikeplan.pipeline.fetch import _load_network

        area = AreaSpec.from_city("Test City")
        self.assertIsNone(area.bbox)

        gdf_edges = gpd.GeoDataFrame(
            {"highway": ["residential"]},
            geometry=[LineString([(10.0, 45.0), (10.5, 45.5)])],
            crs="EPSG:4326",
        )
        gdf_nodes = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        gdf_buildings = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        with mock.patch("ltsbikeplan.pipeline.fetch.GraphLoaderService") as mock_loader_cls:
            loader = mock_loader_cls.return_value
            loader.download_graph.return_value = (None, gdf_nodes, gdf_edges)
            loader.filter_major_roads.return_value = gdf_edges
            loader.fetch_building_data.return_value = gdf_buildings

            _, _, _, out_area = _load_network(area, cache_dir="/tmp")

        self.assertIsNotNone(out_area.bbox)
        west, south, east, north = out_area.bbox
        self.assertAlmostEqual(west, 10.0)
        self.assertAlmostEqual(south, 45.0)
        self.assertAlmostEqual(east, 10.5)
        self.assertAlmostEqual(north, 45.5)


if __name__ == "__main__":
    unittest.main()
