import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    from ltsbikeplan.domain.gap_analysis import HIGH_STRESS_LTS, LOW_STRESS_LTS
    from ltsbikeplan.domain.routing_cost import (
        FATIGUE_PENALTY,
        LTS_PENALTY,
        STRESS_RUN_PENALTY,
        SURFACE_FATIGUE_PENALTY,
        edge_cost,
    )

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
        length = 600.0
        costs = [edge_cost(1, length, slope_class) for slope_class in FATIGUE_PENALTY]
        # FATIGUE_PENALTY's own insertion order is flat -> impossible.
        self.assertEqual(costs, sorted(costs))
        self.assertLess(edge_cost(1, length, "0-3: flat"), edge_cost(1, length, "8-10: hard"))

    def test_short_edge_still_gets_the_fatigue_penalty(self):
        # Regression test for a real bug: an earlier version gated the
        # fatigue penalty on length_m >= 500 (mirroring lts_rules.py's own
        # DEM-noise threshold for its LTS-class bump). On a real steep road
        # (Trento's Passo Cimirlo) EVERY one of ~500 edges was under 500m
        # (median ~11m - mountain roads are chopped into many short
        # segments per curve), so that gate silently zeroed out the
        # penalty for the entire climb and the router kept picking it. A
        # short edge - even a few meters - must still be penalized: see
        # edge_cost's own comment for why that's safe (cost is already
        # length-scaled, so a wrong reading here can't skew total path
        # cost by more than a few meters either way).
        short = 11.0
        self.assertGreater(edge_cost(1, short, "10-20: extreme"), edge_cost(1, short, None))
        self.assertEqual(
            edge_cost(1, short, "10-20: extreme"),
            short * LTS_PENALTY[1] * FATIGUE_PENALTY["10-20: extreme"],
        )

    def test_unrecognized_slope_class_falls_back_to_neutral(self):
        length = 600.0
        self.assertEqual(edge_cost(1, length, "not-a-real-class"), edge_cost(1, length, None))

    def test_every_fatigue_multiplier_is_at_least_one(self):
        # web/routing.js's A* heuristic (_MIN_PENALTY) assumes fatigue can
        # only make an edge MORE expensive, never cheaper - a value < 1.0
        # here would silently break heuristic admissibility client-side.
        for multiplier in FATIGUE_PENALTY.values():
            self.assertGreaterEqual(multiplier, 1.0)

    def test_no_stress_run_code_matches_pre_stress_run_behaviour(self):
        # Default (no stress_run_code passed) must be identical to
        # edge_cost before STRESS_RUN_PENALTY existed.
        for lts, penalty in LTS_PENALTY.items():
            self.assertEqual(edge_cost(lts, 600.0), 600.0 * penalty)

    def test_longer_named_run_never_cheaper_at_the_same_lts(self):
        # The actual case this fixes: a long, continuously LTS3 street
        # must cost more per meter than a short LTS3 connector of the
        # same class.
        length = 600.0
        costs = [edge_cost(3, length, stress_run_code=code) for code in sorted(STRESS_RUN_PENALTY)]
        self.assertEqual(costs, sorted(costs))
        self.assertLess(edge_cost(3, length, stress_run_code=0), edge_cost(3, length, stress_run_code=4))

    def test_stress_run_penalty_not_applied_to_lts1(self):
        # A long QUIET street is the whole point of this router - it must
        # not be penalized for being long the way a stressful one is.
        length = 600.0
        for code in STRESS_RUN_PENALTY:
            self.assertEqual(edge_cost(1, length, stress_run_code=code), edge_cost(1, length))

    def test_every_stress_run_multiplier_is_at_least_one(self):
        # Same admissibility requirement as FATIGUE_PENALTY above.
        for multiplier in STRESS_RUN_PENALTY.values():
            self.assertGreaterEqual(multiplier, 1.0)

    def test_no_surface_matches_pre_surface_fatigue_behaviour(self):
        # Default (no surface passed) must be identical to edge_cost
        # before SURFACE_FATIGUE_PENALTY existed.
        for lts, penalty in LTS_PENALTY.items():
            self.assertEqual(edge_cost(lts, 600.0), 600.0 * penalty)

    def test_rough_surface_never_cheaper_than_paved_at_the_same_lts(self):
        # The actual case this fixes: Trento's Passo Cimirlo has 1.29km of
        # cobblestone spread across edges too short (median 29m) to ever
        # trip lts_rules.py's own >=500m-per-edge surface_penalty gate -
        # this independent, non-length-gated axis must still see it.
        length = 100.0
        self.assertLess(edge_cost(1, length, surface=None), edge_cost(1, length, surface="cobblestone"))
        self.assertLess(edge_cost(1, length, surface="cobblestone"), edge_cost(1, length, surface="mud"))

    def test_surface_fatigue_not_gated_by_length(self):
        # Unlike lts_rules.py's own surface_penalty (LTS-class bump, gated
        # at >=500m for the moderate tier), this continuous, length-scaled
        # cost must apply even to a single short edge - see
        # test_short_edge_still_gets_the_fatigue_penalty's slope analogue
        # for the full reasoning.
        short = 11.0
        self.assertEqual(
            edge_cost(1, short, surface="gravel"),
            short * LTS_PENALTY[1] * SURFACE_FATIGUE_PENALTY["gravel"],
        )

    def test_unrecognized_surface_falls_back_to_neutral(self):
        length = 600.0
        self.assertEqual(edge_cost(1, length, surface="asphalt"), edge_cost(1, length, surface=None))

    def test_every_surface_fatigue_multiplier_is_at_least_one(self):
        # Same admissibility requirement as FATIGUE_PENALTY above.
        for multiplier in SURFACE_FATIGUE_PENALTY.values():
            self.assertGreaterEqual(multiplier, 1.0)


if __name__ == "__main__":
    unittest.main()
