import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    from ltsbikeplan.domain.gap_analysis import HIGH_STRESS_LTS, LOW_STRESS_LTS
    from ltsbikeplan.domain.routing_cost import LTS_PENALTY, edge_cost

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


if __name__ == "__main__":
    unittest.main()
