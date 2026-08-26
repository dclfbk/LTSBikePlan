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
LTS_PENALTY: dict[int, float] = {1: 1.0, 2: 1.3, 3: 2.5, 4: 6.0}


def edge_cost(lts: int, length_m: float) -> float:
    """Routing cost of one edge: its length, scaled by how much its LTS
    class should be avoided. Unknown/out-of-range `lts` values fall back to
    the LTS 4 (most-penalized) rate rather than raising - conservative
    default for the one caller that also needs it (build_routing_graph.py
    coerces NaN `lts` to 4 explicitly before calling this, but the fallback
    stays here too so this function is safe on its own).
    """
    return length_m * LTS_PENALTY.get(lts, LTS_PENALTY[4])
