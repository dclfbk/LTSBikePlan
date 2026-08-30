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
#
# The gaps between classes (previously 1.0/1.3/2.5/6.0) were narrowed after
# a real-world mismatch: two independent real routes (Trento -> Pergine
# Valsugana, Trento -> an area south of it near Costasavina), compared
# against Valhalla's/OSRM's actual bicycle routing, both showed the same
# pattern - a real provincial road (paved, moderate grade, but LTS3 purely
# because it's a genuinely classified through-road with real traffic, see
# domain/lts_rules.py's mixed_traffic `ref`-based m9/m10 split) kept
# losing to a low-LTS but objectively worse alternative (a steep unpaved
# climb) no matter how much FATIGUE_PENALTY/SURFACE_FATIGUE_PENALTY below
# were strengthened - even at 4x on the worst slope tier, the LTS2->LTS3
# gap alone (1.3x -> 2.5x, applied to the WHOLE length of the classified
# road) still won, because the effort-based penalties only bite on the
# specific rough/steep segments of the alternative, not its whole length.
# Narrowing the LTS gap (validated: both real cases now match Valhalla's
# actual route once FATIGUE_PENALTY was raised alongside it - see that
# table's own comment) was the fix that actually worked; raising the
# effort penalties alone, without this, was not enough.
LTS_PENALTY: dict[int, float] = {1: 1.0, 2: 1.2, 3: 1.6, 4: 3.0}

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
# Raised alongside LTS_PENALTY's own narrowing above (previously
# 1.0/1.05/1.2/1.5/2.0/2.0) - the two changes were validated together, not
# independently: on their own, neither a narrower LTS gap nor a stronger
# fatigue penalty was enough to match real routers' actual choice on two
# real test routes (see LTS_PENALTY's own comment for the specifics).
FATIGUE_PENALTY: dict[str, float] = {
    "0-3: flat": 1.0,
    "3-5: mild": 1.1,
    "5-8: medium": 1.6,
    "8-10: hard": 2.5,
    "10-20: extreme": 4.0,
    ">20: impossible": 4.0,
}

# A third, independent multiplier - LTS_PENALTY and FATIGUE_PENALTY are
# both length-linear: 4km of continuous LTS3 costs exactly 4x what 1km of
# it costs, no more. But that's not how people experience it - a brief
# stint on a busier road (crossing one junction, a short connector) reads
# as a minor inconvenience, while being stuck on the SAME class of road
# for kilometers on end (a long arterial with no quieter alternative
# alongside it) is disproportionately more draining. Real case that
# exposed this: a router comparison found a route via a quiet-but-steep
# direct road cheaper than a shorter, flatter alternative BECAUSE the
# flatter one's LTS3 exposure was ~4.6km in one continuous run versus the
# steep route's ~2.2km - the existing length-linear LTS cost already
# "knew" about that difference in total meters, but had no notion that a
# single unbroken multi-km stretch of it is worse than the same total
# meters spread across several shorter, separated ones.
#
# Keyed by scripts/build_routing_graph.py's stress_run_code - a bucketed
# "how long is the named street's run at this exact LTS class" computed
# once at export time (grouping by (name, lts) across the whole comune),
# NOT a live property of the specific path a rider takes. That's a
# deliberate simplification, not an oversight: a true path-dependent
# version (cost depends on how much of THIS class you've already ridden
# on THIS route) needs the pathfinder itself to carry state per-path
# (ngraph.path's A* only ever sees one edge and its endpoints, nothing
# about the path taken to reach it) - real added complexity and a real
# performance cost for an entirely client-side, in-browser router. A
# precomputed per-street proxy gets most of the same practical benefit
# (genuinely long stressful corridors cost more; short stressful
# connectors don't) without touching the search algorithm at all.
#
# Only applied when lts >= 2 (see edge_cost below) - a long QUIET street
# is exactly what this router is trying to find more of, not something to
# penalize for being long.
STRESS_RUN_PENALTY: dict[int, float] = {
    0: 1.0,   # < 200m
    1: 1.0,   # 200-500m - still a short connector, not a sustained exposure
    2: 1.15,  # 500-1500m
    3: 1.35,  # 1500-3000m
    4: 1.6,   # > 3000m - a genuinely long, continuously stressful corridor
}

# A fourth, independent multiplier, same spirit as FATIGUE_PENALTY: surface
# quality is physical effort, not traffic stress, so it's kept separate
# from LTS_PENALTY too. domain/lts_rules.py's BikePathAnalysis.
# surface_penalty already bumps LTS for a rough surface, but that bump is
# gated behind a >=500m-per-edge threshold (same DEM-noise-style
# reasoning FATIGUE_PENALTY's own gate used to have, see that table's
# comment) - real case that exposed the gap: Trento's Passo Cimirlo has
# 1.29km of cobblestone/paving_stones surface, but spread across 40 edges
# with a MEDIAN length of 29m, so not one of them ever reaches 500m and
# the whole stretch scores zero surface penalty anywhere - not in LTS, and
# (until this table) not in routing cost either.
#
# Values mirror lts_rules.py's own two-tier split (_MODERATE_SURFACE_
# VALUES/_SEVERE_SURFACE_VALUES) - keys are the raw OSM `surface` tag
# values themselves, not re-bucketed here, so a change to either set there
# must be mirrored here too or the newly (un)covered value(s) silently
# fall back to the neutral 1.0 multiplier.
SURFACE_FATIGUE_PENALTY: dict[str, float] = {
    # Moderate - rideable on most bikes with extra effort.
    "compacted": 1.3,
    "fine_gravel": 1.3,
    "gravel": 1.3,
    "sett": 1.3,
    "cobblestone": 1.3,
    "unhewn_cobblestone": 1.3,
    "woodchips": 1.3,
    "unpaved": 1.3,
    # Severe - meaningfully harder or risky, especially wet.
    "ground": 1.8,
    "dirt": 1.8,
    "earth": 1.8,
    "sand": 1.8,
    "mud": 1.8,
    "grass": 1.8,
    "pebblestone": 1.8,
    "ice": 1.8,
    "snow": 1.8,
}

# NOTE - deliberately NOT gated by lts_rules.py's own
# MIN_RELIABLE_SLOPE_LENGTH_M (500m), even though this table's keys come
# from that same module. An earlier version of this function copied that
# gate here too, reasoning "same DEM-noise concern, same threshold" - that
# was wrong, and measurably so: checked against a real steep road (Trento's
# Passo Cimirlo, ~500 edges) after that version shipped, EVERY edge was
# under 500m (median ~11m - mountain roads get chopped into many short
# segments per curve), so the "reliable" gate silently zeroed out the
# fatigue penalty for the entire climb, defeating this feature outright.
# Re-tested with the gate removed on the same real road network (Trento/
# Pergine area): the router now avoids that climb.
#
# The two uses aren't actually the same risk. lts_rules.py's gate protects
# a discrete, visible classification - bumping one specific edge's
# DISPLAYED LTS class a whole step on a wrong reading is a real, sticky
# mistake. Here the output is a continuous cost that's already scaled by
# `length_m`: a wrongly-classified 10m edge can only ever miscount the
# path's total cost by a few meters either way, lost in the noise of a
# multi-km route - self-limiting in a way a class jump isn't. Blocking the
# penalty below some length trades that small, bounded risk for a much
# bigger one: it silently no-ops on exactly the finely-segmented roads
# real climbs tend to be made of.
def edge_cost(
    lts: int,
    length_m: float,
    slope_class: str | None = None,
    stress_run_code: int | None = None,
    surface: str | None = None,
) -> float:
    """Routing cost of one edge: its length, scaled by how much its LTS
    class should be avoided, further scaled by how physically tiring it
    is (independent of LTS - see FATIGUE_PENALTY above), further scaled by
    how long a continuously-stressful street this edge belongs to (see
    STRESS_RUN_PENALTY above), further scaled by how rough its surface is
    (see SURFACE_FATIGUE_PENALTY above). Unknown/out-of-range `lts` values
    (LTS 0 included - see the module comment on why that's wrong for a
    *routable* edge) fall back to the LTS 4 (most-penalized) rate rather
    than raising - conservative default for the one caller that also
    needs it (build_routing_graph.py coerces NaN `lts` to 4 explicitly
    before calling this, but the fallback stays here too so this function
    is safe on its own). Callers that might see LTS 0 - i.e. anything
    reading `all_lts` directly rather than an already-filtered routing
    export - must exclude it themselves; this function has no way to tell
    "unusual but real" apart from "not a road you can route on".

    `slope_class`/`stress_run_code`/`surface` all default to None (no
    extra penalty applied, same as this function's behaviour before any
    of them existed) - callers that don't have the relevant data for an
    edge should pass None rather than guessing a value, per this
    codebase's "don't penalize missing data" convention (see
    lts_rules.py). An unrecognized `slope_class`/`surface` string also
    falls back to the neutral 1.0 multiplier, same treatment as None;
    `stress_run_code` is only ever looked up when `lts >= 2` (see
    STRESS_RUN_PENALTY's own comment on why a long QUIET street shouldn't
    be penalized for being long).
    """
    lts_multiplier = LTS_PENALTY.get(lts, LTS_PENALTY[4])
    fatigue_multiplier = 1.0 if slope_class is None else FATIGUE_PENALTY.get(slope_class, 1.0)
    stress_run_multiplier = 1.0
    if stress_run_code is not None and lts >= 2:
        stress_run_multiplier = STRESS_RUN_PENALTY.get(stress_run_code, 1.0)
    surface_fatigue_multiplier = 1.0 if surface is None else SURFACE_FATIGUE_PENALTY.get(surface, 1.0)
    return length_m * lts_multiplier * fatigue_multiplier * stress_run_multiplier * surface_fatigue_multiplier
