from __future__ import annotations

import geopandas as gpd
import pandas as pd


def annotate_parallel_cycleway(
    all_lts: gpd.GeoDataFrame,
    buffer_m: float = 30.0,
    coverage_threshold: float = 0.75,
) -> gpd.GeoDataFrame:
    """Flags high-stress "gap" edges (domain/gap_analysis.py's is_gap_edge)
    that run alongside an existing separated cycle path for most of their
    length - a rider already has a low-stress alternative there, so the
    street itself is a weak candidate for the priority-interventions list
    even though its own LTS is high.

    `all_lts` must already be in a metric CRS (WORKING_CRS) - buffer_m is
    interpreted in the GeoDataFrame's own CRS units, so compute_lts.py only
    reaches this step after reprojecting off the source lon/lat CRS.

    Coverage is (length of the road within buffer_m of a separated path) /
    (road length) - not a bearing check. A cycleway crossing the road
    perpendicularly only covers about 2*buffer_m of it, which stays well
    under coverage_threshold for anything but a very short road, so no
    separate direction test is needed. "Separated path" reuses
    domain/lts_rules.py::BikePathAnalysis.is_separated_path's own output
    (rule codes s1/s2/s3/s7/s8, forced to lts=1) rather than re-deriving it
    from raw tags.
    """
    all_lts = all_lts.copy()
    # Built as one Series and assigned to each column exactly once at the
    # end (rather than initializing default columns and mutating them in
    # place via .loc) - the mutate-then-reassign pattern trips pandas'
    # copy-on-write chained-assignment detector on a GeoDataFrame, even
    # though every write here already goes through .loc/a full-column
    # assignment.
    coverage = pd.Series(0.0, index=all_lts.index)

    is_separated = all_lts["rule"].astype(str).str.startswith("s")
    cycleways = all_lts[is_separated]
    candidates = all_lts[all_lts["is_gap_edge"] == True]  # noqa: E712

    if not cycleways.empty and not candidates.empty:
        cycleway_sindex = cycleways.sindex
        for idx, road_geom in candidates.geometry.items():
            if road_geom is None or road_geom.is_empty:
                continue
            road_length = road_geom.length
            if road_length <= 0:
                continue

            nearby_positions = list(cycleway_sindex.intersection(road_geom.buffer(buffer_m).bounds))
            if not nearby_positions:
                continue

            nearby_buffer = cycleways.geometry.iloc[nearby_positions].buffer(buffer_m).union_all()
            overlap_length = road_geom.intersection(nearby_buffer).length
            coverage.loc[idx] = overlap_length / road_length

    all_lts["parallel_cycleway_coverage"] = coverage
    all_lts["has_parallel_cycleway"] = coverage >= coverage_threshold
    return all_lts
