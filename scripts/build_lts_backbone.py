#!/usr/bin/env python3
"""Dissolves contiguous same-LTS road segments into long corridors, for the
national low-zoom "italia" overview (web/index.html?area=italia, z4-11).

WHY THIS EXISTS - see the analysis in this repo's history (ltsbikeplan
project chat, Aug 2026): a plain LTS+centrality tippecanoe filter on the
per-edge data (scripts/build_national_tiles.sh's old LTS_VISIBILITY_FILTER
attempt) produced ZERO visible features at z4-11, in every case tested
(both dense cities and rural comuni). Root cause: every edge in
compute-lts's own graph (u/v/key - one edge per intersection-to-intersection
segment) is short - measured median ~11-20m, even for "important" edges by
centrality. At z4-11 (roughly 100-1000+ m/pixel), a 15m line is sub-pixel
and tippecanoe's own line simplification drops it before any -j filter or
--coalesce gets a chance - --coalesce specifically failed here too, because
it requires an EXACT match on every retained property (including `rule`,
which differs edge-to-edge even at the same lts).

THE FIX: do the merging ourselves, with real geometry, before tippecanoe
ever sees the data. shapely.ops.linemerge stitches LineStrings that share
an endpoint into one longer LineString - so a quiet street built from
thirty 15m fragments becomes one ~450m line, comfortably visible at z7-8+.
Grouping is by (comune, lts) only (NOT highway/rule/name) to maximize how
much merges - the backbone layer this feeds is a "here's the low-stress
network" overview, not the detailed/interactive one (that's still the
existing per-comune _lts.pmtiles, unaffected by any of this).

OUTPUT: one GeoJSON (default web/data/lts_backbone.geojson) of merged
corridors with a `lts` property (int) and a `length_m` property (the merged
corridor's own real length, in meters - used both to filter and, for
tippecanoe, as an alternative to `centrality` since a merged corridor's
length is already a decent "is this locally significant" signal on its
own - long quiet corridors are the ones a rider would actually plan a route
around). MIN_CORRIDOR_LENGTH_M drops anything that dissolving still leaves
short (a genuinely isolated quiet cul-de-sac, not a through corridor) -
tune this against a real test build (see build_national_tiles.sh's own
comment block for how to sanity-check tile density before a full national
run).

NOT wired into build_national_tiles.sh yet - see that script's own comment
for the two lines to add once this has been run. Run this ONCE against a
full `data/` (all comuni reprocessed), not per-batch like the main tile
build - the output is small enough (a few thousand merged corridors
nationwide, not millions of raw edges) that there's no batching/disk
concern here like there is for the full per-comune GeoJSON regeneration.

Usage:
  source .venv/bin/activate
  PYTHONPATH=code python3 scripts/build_lts_backbone.py \
      [--data-dir data] [--out web/data/lts_backbone.geojson] \
      [--min-length-m 300] [--lts 1,2,3]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

import geopandas as gpd
from shapely.geometry import mapping
from shapely.ops import linemerge


def dissolve_comune(gdf: gpd.GeoDataFrame, lts_values: set[int]) -> list[dict]:
    """One comune's edges -> a list of merged-corridor GeoJSON-ready dicts.

    Grouped by `lts` only (see module docstring for why highway/rule/name
    aren't part of the group key) - linemerge takes care of only actually
    stitching segments that share a real endpoint, so grouping too broadly
    (e.g. "all of lts=2 in this comune") is safe: disconnected clusters
    just come back as separate lines in the resulting MultiLineString,
    nothing gets wrongly joined across a gap.
    """
    out = []
    sub = gdf[gdf["lts"].isin(lts_values)]
    for lts_value, group in sub.groupby("lts"):
        geoms = list(group.geometry)
        if not geoms:
            continue
        merged = linemerge(geoms)
        # linemerge returns a single LineString if everything joined into
        # one piece, or a MultiLineString if there are several disjoint
        # pieces - normalize to a flat list of LineStrings either way.
        pieces = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
        for piece in pieces:
            # Length in metres: geometry here is already in the parquet's
            # WORKING_CRS (EPSG:3035, a metric equal-area projection - see
            # regenerate_geojson.py's own note on this), so .length is
            # already metres, no reprojection needed.
            length_m = piece.length
            out.append({"lts": int(lts_value), "length_m": length_m, "geometry": piece})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out", default="web/data/lts_backbone.geojson")
    parser.add_argument(
        "--min-length-m",
        type=float,
        default=300.0,
        help="Drop merged corridors shorter than this (still sub-pixel-ish at low zoom, or just a short isolated cul-de-sac, not a through corridor).",
    )
    parser.add_argument(
        "--lts",
        default="1,2,3",
        help="Comma-separated LTS values to include (default: 1,2,3 - matches the z8-11 'highlight' tier; use 1,2 for a smaller z4-7-only backbone if the combined one proves too dense).",
    )
    args = parser.parse_args()

    lts_values = {int(v) for v in args.lts.split(",")}
    files = sorted(glob.glob(os.path.join(args.data_dir, "*", "*_all_lts.parquet")))
    print(f"{len(files)} comuni found under {args.data_dir}", flush=True)

    all_rows: list[dict] = []
    for i, f in enumerate(files):
        gdf = gpd.read_parquet(f, columns=["lts", "geometry"])
        all_rows.extend(dissolve_comune(gdf, lts_values))
        if i % 500 == 0:
            print(f"  ...{i}/{len(files)} comuni dissolved, {len(all_rows)} corridors so far", flush=True)

    print(f"Dissolved into {len(all_rows)} raw corridors (pre length-filter)", flush=True)

    kept = [r for r in all_rows if r["length_m"] >= args.min_length_m]
    print(f"{len(kept)} corridors kept (>= {args.min_length_m}m), {len(all_rows) - len(kept)} dropped as too short", flush=True)

    # Reproject back to WGS84 for GeoJSON (same as regenerate_geojson.py /
    # ExportService.write_geojson does for the per-comune output) - tippecanoe
    # needs lon/lat, not the metric working CRS the merge was computed in.
    gdf_out = gpd.GeoDataFrame(kept, geometry="geometry", crs="EPSG:3035").to_crs("EPSG:4326")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    features = []
    for _, row in gdf_out.iterrows():
        features.append(
            {
                "type": "Feature",
                "properties": {"lts": row["lts"], "length_m": round(row["length_m"])},
                "geometry": mapping(row.geometry),
            }
        )
    with open(args.out, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh)

    total_km = sum(r["length_m"] for r in kept) / 1000
    print(f"Wrote {args.out}: {len(features)} corridors, {total_km:.0f} km total", flush=True)


if __name__ == "__main__":
    main()
