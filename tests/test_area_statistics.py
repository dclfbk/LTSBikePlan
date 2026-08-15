import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.domain.area_statistics import compute_area_statistics


class TestComputeAreaStatistics(unittest.TestCase):
    def _base_frame(self, rows):
        defaults = {
            "length": 0.0,
            "lts": 0,
            "rule": "m0",
            "is_gap_edge": False,
            "has_parallel_cycleway": False,
            "gap_component": None,
        }
        filled = [{**defaults, **row} for row in rows]
        return pd.DataFrame(filled)

    def test_total_km_sums_all_lengths(self):
        all_lts = self._base_frame([{"length": 1000.0}, {"length": 2000.0}])
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["total_km"], 3.0)
        self.assertEqual(stats["area"], "test-area")

    def test_km_by_lts_buckets_each_class(self):
        all_lts = self._base_frame(
            [
                {"length": 1000.0, "lts": 0},
                {"length": 2000.0, "lts": 1},
                {"length": 3000.0, "lts": 2},
                {"length": 4000.0, "lts": 3},
                {"length": 5000.0, "lts": 4},
            ]
        )
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["km_by_lts"], {"0": 1.0, "1": 2.0, "2": 3.0, "3": 4.0, "4": 5.0})

    def test_low_stress_share_excludes_lts_zero(self):
        # 1km lts=0 (excluded from denominator), 1km lts=1 (low), 1km lts=4
        # (high) -> share should be 0.5, not 1/3.
        all_lts = self._base_frame(
            [
                {"length": 1000.0, "lts": 0},
                {"length": 1000.0, "lts": 1},
                {"length": 1000.0, "lts": 4},
            ]
        )
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["low_stress_share"], 0.5)

    def test_low_stress_share_is_none_when_nothing_classified(self):
        all_lts = self._base_frame([{"length": 1000.0, "lts": 0}])
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertIsNone(stats["low_stress_share"])

    def test_separated_path_km_excludes_mountain_trail_rule(self):
        all_lts = self._base_frame(
            [
                {"length": 1000.0, "rule": "s1"},
                {"length": 1000.0, "rule": "s3"},
                {"length": 1000.0, "rule": "s9"},  # mountain trail - not comfortable
            ]
        )
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["separated_path_km"], 2.0)
        self.assertEqual(stats["excluded_mountain_trail_km"], 1.0)

    def test_priority_intervention_km_excludes_parallel_cycleway(self):
        all_lts = self._base_frame(
            [
                {"length": 1000.0, "is_gap_edge": True, "has_parallel_cycleway": False},
                {"length": 1000.0, "is_gap_edge": True, "has_parallel_cycleway": True},
                {"length": 1000.0, "is_gap_edge": False, "has_parallel_cycleway": False},
            ]
        )
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["priority_intervention_km"], 1.0)

    def test_excluded_motorroad_km(self):
        all_lts = self._base_frame([{"length": 1000.0, "rule": "p10"}, {"length": 1000.0, "rule": "m6"}])
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["excluded_motorroad_km"], 1.0)

    def test_low_stress_island_count_and_km(self):
        all_lts = self._base_frame(
            [
                {"length": 1000.0, "gap_component": "test-area:0"},
                {"length": 1000.0, "gap_component": "test-area:0"},
                {"length": 2000.0, "gap_component": "test-area:1"},
                {"length": 500.0, "gap_component": None},
            ]
        )
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["low_stress_island_count"], 2)
        self.assertEqual(stats["low_stress_island_km"], 4.0)

    def test_missing_optional_columns_does_not_crash(self):
        all_lts = pd.DataFrame({"length": [1000.0], "lts": [2], "rule": ["b1"]})
        stats = compute_area_statistics(all_lts, "test-area")
        self.assertEqual(stats["priority_intervention_km"], 0.0)
        self.assertEqual(stats["low_stress_island_count"], 0)
        self.assertEqual(stats["low_stress_island_km"], 0.0)


if __name__ == "__main__":
    unittest.main()
