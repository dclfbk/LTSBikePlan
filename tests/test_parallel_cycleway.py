import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import geopandas as gpd
    from shapely.geometry import LineString

    from ltsbikeplan.domain.parallel_cycleway import annotate_parallel_cycleway

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/shapely (geo extras) not installed")
class TestAnnotateParallelCycleway(unittest.TestCase):
    def _gdf(self, rows):
        return gpd.GeoDataFrame(rows, crs="EPSG:3035")

    def test_road_fully_alongside_a_cycleway_is_flagged(self):
        # Cycleway runs 10m off the road for the road's whole 1000m length -
        # well within a 30m buffer.
        rows = [
            {"rule": "m12", "is_gap_edge": True, "geometry": LineString([(0, 0), (1000, 0)])},
            {"rule": "s3", "is_gap_edge": False, "geometry": LineString([(0, 10), (1000, 10)])},
        ]
        annotated = annotate_parallel_cycleway(self._gdf(rows))
        road = annotated.iloc[0]
        self.assertTrue(road["has_parallel_cycleway"])
        self.assertGreater(road["parallel_cycleway_coverage"], 0.95)

    def test_cycleway_crossing_perpendicularly_is_not_flagged(self):
        # Crosses the road once, at a right angle - only ~2*buffer_m of the
        # road falls inside the buffered cycleway, nowhere near the 75%
        # coverage threshold.
        rows = [
            {"rule": "m12", "is_gap_edge": True, "geometry": LineString([(0, 100), (1000, 100)])},
            {"rule": "s3", "is_gap_edge": False, "geometry": LineString([(500, 50), (500, 150)])},
        ]
        annotated = annotate_parallel_cycleway(self._gdf(rows))
        road = annotated.iloc[0]
        self.assertFalse(road["has_parallel_cycleway"])
        self.assertLess(road["parallel_cycleway_coverage"], 0.75)

    def test_cycleway_alongside_only_part_of_the_road_is_below_threshold(self):
        # Parallel for only the first 300m of a 1000m road.
        rows = [
            {"rule": "m12", "is_gap_edge": True, "geometry": LineString([(0, 200), (1000, 200)])},
            {"rule": "s3", "is_gap_edge": False, "geometry": LineString([(0, 210), (300, 210)])},
        ]
        annotated = annotate_parallel_cycleway(self._gdf(rows))
        road = annotated.iloc[0]
        self.assertGreater(road["parallel_cycleway_coverage"], 0.0)
        self.assertLess(road["parallel_cycleway_coverage"], 0.75)
        self.assertFalse(road["has_parallel_cycleway"])

    def test_non_gap_edge_is_never_evaluated(self):
        # Even with a perfectly parallel cycleway, a road that isn't a gap
        # edge in the first place isn't a candidate to begin with.
        rows = [
            {"rule": "m12", "is_gap_edge": False, "geometry": LineString([(0, 0), (1000, 0)])},
            {"rule": "s3", "is_gap_edge": False, "geometry": LineString([(0, 10), (1000, 10)])},
        ]
        annotated = annotate_parallel_cycleway(self._gdf(rows))
        road = annotated.iloc[0]
        self.assertFalse(road["has_parallel_cycleway"])
        self.assertEqual(road["parallel_cycleway_coverage"], 0.0)

    def test_no_cycleways_present_leaves_defaults(self):
        rows = [{"rule": "m12", "is_gap_edge": True, "geometry": LineString([(0, 0), (1000, 0)])}]
        annotated = annotate_parallel_cycleway(self._gdf(rows))
        road = annotated.iloc[0]
        self.assertFalse(road["has_parallel_cycleway"])
        self.assertEqual(road["parallel_cycleway_coverage"], 0.0)

    def test_coverage_threshold_is_configurable(self):
        rows = [
            {"rule": "m12", "is_gap_edge": True, "geometry": LineString([(0, 200), (1000, 200)])},
            {"rule": "s3", "is_gap_edge": False, "geometry": LineString([(0, 210), (300, 210)])},
        ]
        annotated = annotate_parallel_cycleway(self._gdf(rows), coverage_threshold=0.3)
        self.assertTrue(annotated.iloc[0]["has_parallel_cycleway"])


if __name__ == "__main__":
    unittest.main()
