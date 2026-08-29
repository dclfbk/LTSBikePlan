from __future__ import annotations

# Soft LTS preference for client-side routing (scripts/build_routing_graph.py,
# web/routing.js) - NOT a hard filter. The low-stress network has real
# connectivity gaps (see domain/gap_analysis.py), so a router that refuses
# LTS 3/4 outright would return "no route" in realistic cases; instead every
# class stays usable, just increasingly penalized.
#
# This table is the single source of truth for the formula - the actual
# per-comune JSON export (scripts/build_routing_graph.py) ships raw
# `lts`/`length_m`, not a precomputed cost, so tuning these numbers never
# requires regenerating every comune's file. web/routing.js's own
# `LTS_PENALTY`/`edgeCost()` mirror this by hand (no shared build step
# between Python and the static site) - if this table changes, update both.
#
# Deliberately has NO entry for LTS 0 ("Non ciclabile" in LTS_COLORS/the
# legend - a road with no bike access at all, e.g. a motorway, not merely a
# stressful one). LTS 0 is not "the worst penalty", it's not a valid choice
# in the first place - build_routing_graph.py drops those edges entirely
# rather than letting them reach this table, so `edge_cost` is never
# actually called with lts=0 in practice. Don't add a `0: ...` entry here
# as a shortcut instead of fixing the export - that would silently let the
# router draw a route across a road a cyclist can't use (this was a real
# bug: the old fallback below quietly treated 0 the same as 4).
LTS_PENALTY: dict[int, float] = {1: 1.0, 2: 1.3, 3: 2.5, 4: 6.0}

# Independent of LTS_PENALTY. domain/lts_rules.py's BikePathAnalysis.
# slope_penalty already bumps a steep edge's LTS class (e.g. LTS1 -> LTS3),
# but that folds two different things into one number: traffic STRESS and
# physical EFFORT. Two LTS1 streets - one flat, one with a long climb too
# mild/short to trip that bump - cost EXACTLY the same today, because
# edge_cost only ever saw the integer `lts` class, never the underlying
# slope. FATIGUE_PENALTY is a second, independent multiplier so that, at
# the SAME LTS class, the flatter option always wins - which is the actual
# bug report this fixes: the router was picking long-climb quiet streets
# over slightly-busier flat ones purely because within-class differences
# were invisible to it.
#
# This is deliberately symmetric - it can't distinguish uphill from
# downhill. The DEM-derived `slope` it reads (services/slope_strategies.py)
# is an unsigned gradient magnitude: the same edge looks equally "steep"
# ridden in either direction, since no per-node elevation is sampled
# anywhere in this pipeline yet. So this only ever answers "how much
# physical effort does crossing this edge take, regardless of direction" -
# not "is this a climb or a descent for this rider, right now". Don't read
# a directional intent into it.
#
# Keys are domain/lts_rules.py's own slope_class labels (BikePathAnalysis.
# slope_penalty's pd.cut breaks/labels), not re-bucketed here - if that
# pd.cut call's labels ever change, this table must change with it or
# every edge will silently fall back to the neutral 1.0 multiplier below.
FATIGUE_PENALTY: dict[str, float] = {
    "0-3: flat": 1.0,
    "3-5: mild": 1.05,
    "5-8: medium": 1.2,
    "8-10: hard": 1.5,
    "10-20: extreme": 2.0,
    ">20: impossible": 2.0,
}

# Mirrors lts_rules.py's slope_penalty's own MIN_RELIABLE_SLOPE_LENGTH_M
# (see that function's comment for the full DEM-noise rationale: a short
# edge crosses too few raster cells for its mean slope to mean anything).
# Below this length, `slope_class` is measurement noise, not a real grade,
# so it's not trustworthy enough to move a route's cost either - such an
# edge gets the neutral 1.0 fatigue multiplier regardless of its
# slope_class value.
MIN_RELIABLE_SLOPE_LENGTH_M = 500


def edge_cost(lts: int, length_m: float, slope_class: str | None = None) -> float:
    """Routing cost of one edge: its length, scaled by how much its LTS
    class should be avoided, further scaled by how physically tiring it
    is (independent of LTS - see FATIGUE_PENALTY above). Unknown/out-of-
    range `lts` values (LTS 0 included - see the module comment on why
    that's wrong for a *routable* edge) fall back to the LTS 4 (most-
    penalized) rate rather than raising - conservative default for the one
    caller that also needs it (build_routing_graph.py coerces NaN `lts` to
    4 explicitly before calling this, but the fallback stays here too so
    this function is safe on its own). Callers that might see LTS 0 - i.e.
    anything reading `all_lts` directly rather than an already-filtered
    routing export - must exclude it themselves; this function has no way
    to tell "unusual but real" apart from "not a road you can route on".

    `slope_class` defaults to None (no fatigue penalty applied, same as
    this function's behaviour before FATIGUE_PENALTY existed) - callers
    that don't have a reliable slope reading for an edge (too short, no
    DEM coverage) should pass None rather than guessing a value, per this
    codebase's "don't penalize missing data" convention (see lts_rules.py).
    An unrecognized string also falls back to the neutral 1.0 multiplier,
    same treatment as None.
    """
    lts_multiplier = LTS_PENALTY.get(lts, LTS_PENALTY[4])
    fatigue_multiplier = 1.0
    if slope_class is not None and length_m >= MIN_RELIABLE_SLOPE_LENGTH_M:
        fatigue_multiplier = FATIGUE_PENALTY.get(slope_class, 1.0)
    return length_m * lts_multiplier * fatigue_multiplier
