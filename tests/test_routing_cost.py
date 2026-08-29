import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    from ltsbikeplan.domain.gap_analysis import HIGH_STRESS_LTS, LOW_STRESS_LTS
    from ltsbikeplan.domain.routing_cost import FATIGUE_PENALTY, LTS_PENALTY, MIN_RELIABLE_SLOPE_LENGTH_M, edge_cost

    GEO_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - geo deps optional in this env
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "networkx (geo extras, for gap_analysis) not installed")
class TestEdgeCost(unittest.TestCase):
    def test_penalty_per_lts_class(self):
        for lts, penalty in LTS_PENALTY.items():
            self.assertEqual(edge_cost(lts, 100.0), 100.0 * penalty)

    def test_higher_lts_never_cheaper_for_the_same_length(self):
        costs = [edge_cost(lts, 100.0) for lts in sorted(LTS_PENALTY)]
        self.assertEqual(costs, sorted(costs))

    def test_unknown_lts_falls_back_to_the_worst_penalty(self):
        self.assertEqual(edge_cost(99, 100.0), edge_cost(4, 100.0))

    def test_zero_length_is_zero_cost(self):
        self.assertEqual(edge_cost(1, 0.0), 0.0)

    def test_every_gap_analysis_lts_class_has_a_penalty(self):
        # web/routing.js's LTS_PENALTY mirrors this table by hand - this
        # test only guards the Python side, but at minimum every class
        # domain/gap_analysis.py actually classifies must be covered here.
        for lts in LOW_STRESS_LTS | HIGH_STRESS_LTS:
            self.assertIn(lts, LTS_PENALTY)

    def test_no_slope_class_matches_pre_fatigue_behaviour(self):
        # Default (no slope_class passed) must be identical to edge_cost
        # before FATIGUE_PENALTY existed - every test above relies on this.
        for lts, penalty in LTS_PENALTY.items():
            self.assertEqual(edge_cost(lts, 600.0), 600.0 * penalty)

    def test_steeper_edge_never_cheaper_than_flatter_one_at_same_lts(self):
        # The actual bug report this fixes: two LTS1 edges of the same
        # length must NOT cost the same once one of them is steep - the
        # flatter one should always win.
        length = 600.0  # >= MIN_RELIABLE_SLOPE_LENGTH_M
        costs = [edge_cost(1, length, slope_class) for slope_class in FATIGUE_PENALTY]
        # FATIGUE_PENALTY's own insertion order is flat -> impossible.
        self.assertEqual(costs, sorted(costs))
        self.assertLess(edge_cost(1, length, "0-3: flat"), edge_cost(1, length, "8-10: hard"))

    def test_short_edge_ignores_slope_class(self):
        # Below MIN_RELIABLE_SLOPE_LENGTH_M the slope reading is DEM noise
        # (see lts_rules.py's own reliability gate) - must not move cost.
        short = MIN_RELIABLE_SLOPE_LENGTH_M - 1
        self.assertEqual(edge_cost(1, short, "10-20: extreme"), edge_cost(1, short, None))

    def test_unrecognized_slope_class_falls_back_to_neutral(self):
        length = 600.0
        self.assertEqual(edge_cost(1, length, "not-a-real-class"), edge_cost(1, length, None))

    def test_every_fatigue_multiplier_is_at_least_one(self):
        # web/routing.js's A* heuristic (_MIN_PENALTY) assumes fatigue can
        # only make an edge MORE expensive, never cheaper - a value < 1.0
        # here would silently break heuristic admissibility client-side.
        for multiplier in FATIGUE_PENALTY.values():
            self.assertGreaterEqual(multiplier, 1.0)


if __name__ == "__main__":
    unittest.main()
