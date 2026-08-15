import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    from shapely.geometry import LineString

    import ltsbikeplan.domain.crs as crs_module
    from ltsbikeplan.domain.crs import chunked_to_crs

    GEO_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - geo deps optional in this env
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/shapely (geo extras) not installed")
class TestChunkedToCrs(unittest.TestCase):
    def _gdf(self, n):
        rows = [
            {"id": i, "geometry": LineString([(11.0 + i * 0.001, 45.0), (11.0 + i * 0.001, 45.001)])}
            for i in range(n)
        ]
        return gpd.GeoDataFrame(rows, crs="EPSG:4326")

    def _with_chunk_rows(self, value):
        # _TO_CRS_CHUNK_ROWS is a module global looked up at call time, not
        # bound at def time - patching it here is enough to exercise the
        # chunking branch without building a 50k-row GeoDataFrame per test.
        original = crs_module._TO_CRS_CHUNK_ROWS
        crs_module._TO_CRS_CHUNK_ROWS = value
        self.addCleanup(setattr, crs_module, "_TO_CRS_CHUNK_ROWS", original)

    def test_below_threshold_matches_plain_to_crs(self):
        gdf = self._gdf(5)
        expected = gdf.to_crs("EPSG:3035")
        result = chunked_to_crs(gdf, "EPSG:3035")
        self.assertTrue(result.geometry.geom_equals_exact(expected.geometry, tolerance=1e-6).all())

    def test_chunking_matches_plain_to_crs(self):
        self._with_chunk_rows(3)
        gdf = self._gdf(10)
        expected = gdf.to_crs("EPSG:3035")
        result = chunked_to_crs(gdf, "EPSG:3035")

        self.assertEqual(len(result), 10)
        self.assertEqual(result.crs, expected.crs)
        self.assertTrue(
            result.geometry.reset_index(drop=True).geom_equals_exact(
                expected.geometry.reset_index(drop=True), tolerance=1e-6
            ).all()
        )

    def test_preserves_non_geometry_columns_and_row_order(self):
        self._with_chunk_rows(4)
        gdf = self._gdf(9)
        result = chunked_to_crs(gdf, "EPSG:3035")
        self.assertListEqual(list(result["id"]), list(range(9)))

    def test_uneven_final_chunk(self):
        # 7 rows over a chunk size of 3 leaves a final chunk of 1 - make
        # sure the last partial chunk isn't dropped.
        self._with_chunk_rows(3)
        gdf = self._gdf(7)
        result = chunked_to_crs(gdf, "EPSG:3035")
        self.assertEqual(len(result), 7)


if __name__ == "__main__":
    unittest.main()
