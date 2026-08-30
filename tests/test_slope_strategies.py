import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import LineString

    from ltsbikeplan.services.slope_strategies import slope_from_dem

    GEO_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - geo deps optional in this env
    GEO_DEPS_AVAILABLE = False


def _write_dem(path, elevation_grid, origin_x=0.0, origin_y=100.0, pixel_size=10.0, crs="EPSG:3857", nodata=None):
    # origin_y is the TOP-left corner (rasterio's convention: y decreases
    # downward) - elevation_grid[0] is the northernmost row.
    transform = from_origin(origin_x, origin_y, pixel_size, pixel_size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=elevation_grid.shape[0],
        width=elevation_grid.shape[1],
        count=1,
        dtype="float64",
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(elevation_grid, 1)


@contextmanager
def _tmp_dem_path():
    fd, path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    try:
        yield path
    finally:
        os.remove(path)


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/rasterio/shapely (geo extras) not installed")
class TestSlopeFromDem(unittest.TestCase):
    def _edges_gdf(self, geometries, lengths):
        return gpd.GeoDataFrame({"length": lengths, "geometry": geometries}, crs="EPSG:3857")

    def test_flat_terrain_gives_zero_slope(self):
        # A 10x10 grid, every cell at the same elevation - any edge on it
        # must read as flat (0%), regardless of geometry.
        with _tmp_dem_path() as dem_path:
            _write_dem(dem_path, np.full((10, 10), 500.0))
            edges = self._edges_gdf([LineString([(5, 95), (95, 95)])], [90.0])
            result = slope_from_dem(edges, dem_path)
            self.assertAlmostEqual(result["slope"].iloc[0], 0.0, places=6)
            self.assertEqual(result["slope_class"].iloc[0], "0-3: flat")

    def test_known_grade_matches_rise_over_run(self):
        # Elevation ramps up 1m per column (10m pixel spacing) - a line
        # from column 5 to column 95 (row 95, i.e. near the bottom) climbs
        # exactly 9 columns * 1m = 9m of real elevation between its two
        # sampled endpoints.
        with _tmp_dem_path() as dem_path:
            grid = np.tile(np.arange(10, dtype=float), (10, 1))  # column i -> elevation i
            _write_dem(dem_path, grid)
            edges = self._edges_gdf([LineString([(5, 5), (95, 5)])], [90.0])
            result = slope_from_dem(edges, dem_path)
            # column at x=5 -> col 0 (elev 0), column at x=95 -> col 9 (elev 9)
            self.assertAlmostEqual(result["slope"].iloc[0], 100.0 * 9.0 / 90.0, places=3)

    def test_uses_the_edges_own_length_column_not_reprojected_geometry_length(self):
        # The whole point of NOT using geometry.length (see slope_from_dem's
        # docstring: Web Mercator's projected meters overstate true ground
        # distance away from the equator) - here the geometry's own planar
        # length (90m) deliberately differs from the `length` column (45m,
        # simulating what a real edge's pre-existing osmnx length would be
        # after CRS distortion correction). The computed grade must divide
        # by 45, not 90.
        with _tmp_dem_path() as dem_path:
            grid = np.tile(np.arange(10, dtype=float), (10, 1))
            _write_dem(dem_path, grid)
            edges = self._edges_gdf([LineString([(5, 5), (95, 5)])], [45.0])
            result = slope_from_dem(edges, dem_path)
            self.assertAlmostEqual(result["slope"].iloc[0], 100.0 * 9.0 / 45.0, places=3)

    def test_multi_vertex_line_sums_absolute_rise_not_net_change(self):
        # Up-then-down profile: same start/end elevation (net change 0),
        # but a real cyclist still climbs partway through. Cumulative
        # |rise| between consecutive vertices must reflect that, not
        # collapse to 0 like a naive endpoint-only rise/run would.
        with _tmp_dem_path() as dem_path:
            # Row of elevations 0,10,10,20,0 across 5 columns (10m pixels).
            grid = np.tile(np.array([0.0, 10.0, 10.0, 20.0, 0.0]), (5, 1))
            _write_dem(dem_path, grid, origin_y=50.0)
            line = LineString([(5, 25), (15, 25), (25, 25), (35, 25), (45, 25)])
            edges = self._edges_gdf([line], [40.0])
            result = slope_from_dem(edges, dem_path)
            # |10-0| + |10-10| + |20-10| + |0-20| = 10+0+10+20 = 40
            self.assertAlmostEqual(result["slope"].iloc[0], 100.0 * 40.0 / 40.0, places=3)

    def test_nodata_pixel_gives_nan_slope_not_a_bogus_value(self):
        with _tmp_dem_path() as dem_path:
            grid = np.full((10, 10), 500.0)
            grid[9, 9] = -9999.0
            _write_dem(dem_path, grid, nodata=-9999.0)
            # Line's second vertex sits exactly on the nodata pixel (col 9, row 9 -> x=95,y=5).
            edges = self._edges_gdf([LineString([(5, 95), (95, 5)])], [90.0])
            result = slope_from_dem(edges, dem_path)
            self.assertTrue(np.isnan(result["slope"].iloc[0]))
            self.assertTrue(result["slope_class"].isna().iloc[0])

    def test_zero_or_missing_length_gives_nan_not_a_divide_by_zero_crash(self):
        with _tmp_dem_path() as dem_path:
            _write_dem(dem_path, np.full((10, 10), 500.0))
            edges = self._edges_gdf(
                [LineString([(5, 95), (95, 95)]), LineString([(5, 85), (95, 85)])],
                [0.0, float("nan")],
            )
            result = slope_from_dem(edges, dem_path)
            self.assertTrue(np.isnan(result["slope"].iloc[0]))
            self.assertTrue(np.isnan(result["slope"].iloc[1]))

    def test_real_world_regression_gentle_hillside_road_not_read_as_a_cliff(self):
        # The actual bug this fixes: the OLD approach (masking a
        # precomputed per-cell slope raster with the edge's footprint)
        # measurably read Trento's real, gently-graded "Strada Imperiale"
        # as 55-86% grade because a touched raster cell near a nearby
        # quarry cliff dominated the mean. A gentle, uniform 3%-grade
        # hillside (no nearby cliff in this synthetic DEM at all) must
        # read as gentle, not "impossible".
        with _tmp_dem_path() as dem_path:
            # 0.3m elevation gain per 10m pixel along a row = 3% grade.
            grid = np.tile(np.arange(10, dtype=float) * 0.3, (10, 1))
            _write_dem(dem_path, grid)
            edges = self._edges_gdf([LineString([(5, 5), (95, 5)])], [90.0])
            result = slope_from_dem(edges, dem_path)
            self.assertLess(result["slope"].iloc[0], 5.0)
            self.assertIn(result["slope_class"].iloc[0], ["0-3: flat", "3-5: mild"])


if __name__ == "__main__":
    unittest.main()
