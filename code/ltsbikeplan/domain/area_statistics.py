from __future__ import annotations

import pandas as pd

from ltsbikeplan.domain.gap_analysis import HIGH_STRESS_LTS, LOW_STRESS_LTS

# Rule codes BikePathAnalysis.is_separated_path assigns to a comfortable,
# physically-separated facility (LTS 1) - excludes "s9" (a path/footway
# reclassified as an unrideable mountain trail, see domain/lts_rules.py),
# which isn't a comfortable facility despite being a "separated" one.
SEPARATED_PATH_RULES = {"s1", "s2", "s3", "s7", "s8"}


def compute_area_statistics(all_lts: pd.DataFrame, area_slug: str) -> dict:
    """Per-area summary indicators for the cross-comune statistics/comparison
    page (web/comuni.html) - one record per processed area, folded into a
    single national file by the aggregation script alongside
    scripts/build_national_tiles.sh. Reads the same `all_lts` frame
    compute_lts.py already builds (post gap-analysis/centrality/parallel-
    cycleway annotation) - no separate pass over the raw export needed.

    All `*_km` fields are plain floats (kilometres, rounded to 3 decimals -
    metre precision, more than enough for a comparison page). `low_stress_
    share` is a 0-1 fraction, not a 0-100 percentage - format it as a
    percentage at display time.
    """
    length_km = all_lts["length"].fillna(0) / 1000.0

    def km_where(mask) -> float:
        return round(float(length_km[mask].sum()), 3)

    lts = all_lts["lts"]
    rule = all_lts["rule"].astype(str)

    km_by_lts = {str(cls): km_where(lts == cls) for cls in (0, 1, 2, 3, 4)}
    low_stress_km = km_where(lts.isin(LOW_STRESS_LTS))
    high_stress_km = km_where(lts.isin(HIGH_STRESS_LTS))
    # Excludes lts=0 ("not applicable" - motorway, bicycle=no, trunk/
    # motorroad, mountain trails, ...) from the denominator: a share of
    # "how comfortable is the network a cyclist would actually consider"
    # shouldn't be diluted by segments nobody would ride in the first place.
    classified_km = low_stress_km + high_stress_km

    is_gap_edge = all_lts["is_gap_edge"] if "is_gap_edge" in all_lts.columns else pd.Series(False, index=all_lts.index)
    has_parallel_cycleway = (
        all_lts["has_parallel_cycleway"] if "has_parallel_cycleway" in all_lts.columns else pd.Series(False, index=all_lts.index)
    )
    priority_mask = (is_gap_edge == True) & (has_parallel_cycleway != True)  # noqa: E712

    if "gap_component" in all_lts.columns:
        islands = all_lts[all_lts["gap_component"].notna()]
        island_count = int(islands["gap_component"].nunique())
        island_km = round(float((islands["length"].fillna(0) / 1000.0).sum()), 3)
    else:
        island_count = 0
        island_km = 0.0

    return {
        "area": area_slug,
        "total_km": km_where(pd.Series(True, index=all_lts.index)),
        "km_by_lts": km_by_lts,
        "low_stress_km": low_stress_km,
        "high_stress_km": high_stress_km,
        "low_stress_share": round(low_stress_km / classified_km, 4) if classified_km else None,
        "separated_path_km": km_where(rule.isin(SEPARATED_PATH_RULES)),
        "priority_intervention_km": km_where(priority_mask),
        "low_stress_island_count": island_count,
        "low_stress_island_km": island_km,
        "excluded_motorroad_km": km_where(rule == "p10"),
        "excluded_mountain_trail_km": km_where(rule == "s9"),
        "excluded_restricted_access_km": km_where(rule.isin(["p11", "p13"])),
        "excluded_service_road_km": km_where(rule == "p12"),
    }
