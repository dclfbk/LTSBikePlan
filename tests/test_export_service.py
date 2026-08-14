import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    from shapely.geometry import LineString

    from ltsbikeplan.domain.crs import STORAGE_CRS, WORKING_CRS
    from ltsbikeplan.services.export_service import ExportService

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/shapely (geo extras) not installed")
class TestExportService(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        # A short line near Trento, expressed directly in WORKING_CRS
        # (EPSG:3035) coordinates, matching what compute_lts.py hands to
        # ExportService after the CRS fix.
        self.gdf = gpd.GeoDataFrame(
            {"lts": [2]},
            geometry=[LineString([(4396000, 2560000), (4396100, 2560100)])],
            crs=WORKING_CRS,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_geoparquet_round_trips_working_crs(self):
        path = os.path.join(self.tmp_dir.name, "out.parquet")
        ExportService.write_geoparquet(self.gdf, path)
        read_back = gpd.read_parquet(path)
        self.assertEqual(read_back.crs.to_epsg(), int(WORKING_CRS.split(":")[1]))
        self.assertEqual(read_back["lts"].iloc[0], 2)

    def test_geojson_is_reprojected_to_storage_crs(self):
        path = os.path.join(self.tmp_dir.name, "out.geojson")
        ExportService.write_geojson(self.gdf, path)
        read_back = gpd.read_file(path)
        self.assertEqual(read_back.crs.to_epsg(), int(STORAGE_CRS.split(":")[1]))
        # Sanity check the coordinates actually moved into lon/lat range,
        # not just a relabeled CRS tag (the original bug this replaces).
        bounds = read_back.total_bounds
        self.assertTrue(-180 <= bounds[0] <= 180)
        self.assertTrue(-90 <= bounds[1] <= 90)

    def test_geoparquet_creates_parent_directories(self):
        path = os.path.join(self.tmp_dir.name, "nested", "dir", "out.parquet")
        ExportService.write_geoparquet(self.gdf, path)
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
