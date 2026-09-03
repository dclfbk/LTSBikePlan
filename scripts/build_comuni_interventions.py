#!/usr/bin/env python3
"""Per-comune "elenco strade prioritarie" for the stats page
(web/stats/index.html), one small JSON file per comune under
web/data/interventions/<istat_code>.json.

Reuses the exact same aggregation web/app.js's computeGapInterventions()
does client-side from on-screen PMTiles features (is_gap_edge=true,
excluding has_parallel_cycleway, grouped by street name, worst-first:
LTS desc, centrality desc, length desc) - but run once here, offline,
over a comune's WHOLE network rather than just what's in the map
viewport.

Two sources, preferred in this order:
1. data/<slug>/<slug>_all_lts.parquet (columnar, so pulling a handful of
   attribute columns skips the geometry entirely - orders of magnitude
   cheaper than parsing the sibling _all_lts.geojson, which runs 1.8GB
   for Roma) - the fast path when a comune's raw data/<slug>/ folder is
   still around.
2. web/data/<slug>_lts.pmtiles, for any comune whose raw folder is gone -
   read back via services/pmtiles_edges_service.py (see that module's own
   docstring for why this reproduces the parquet losslessly).

Also emits a per-comune `highway_km` breakdown (raw OSM `highway` tag,
summed length over the classified network) - the "distinguere per tipo
di strada" the comuni-stats page wants, without inventing any new
trail/road classification: it reuses the tag as compute_lts.py/OSM left
it, alongside the already-existing excluded_* buckets (motorroad,
mountain-trail, service-road, restricted-access) that domain/
area_statistics.py computes and every <slug>_stats.json already carries -
this script does not recompute those, only rolls highway_km alongside
the intervention list so the per-comune JSON download covers both.

One JSON per comune (not one national file) so the stats page only ever
downloads data for the comune actually being viewed - the interventions
list has no reason to scale with the other ~7900 comuni a visitor isn't
looking at.

Usage: scripts/build_comuni_interventions.py [data_dir]
"""
from __future__ import annotations

import glob
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.pmtiles_edges_service import load_edges_dataframe

TOP_N_STREETS = 30
NEEDED_COLUMNS = [
    "name",
    "highway",
    "length",
    "lts",
    "centrality",
    "centrality_class",
    "is_gap_edge",
    "has_parallel_cycleway",
]

# Not a comune - the merged whole-country tileset (see
# scripts/build_comuni_stats.py's own NON_COMUNE_PMTILES_SLUGS).
NON_COMUNE_PMTILES_SLUGS = {"italia"}


BBOX_COLUMNS = ["bbox_minlon", "bbox_minlat", "bbox_maxlon", "bbox_maxlat"]


def build_from_dataframe(df: pd.DataFrame) -> dict:
    highway_km = (
        df.assign(highway=df["highway"].fillna("sconosciuto"))
        .groupby("highway")["length"]
        .sum()
        .div(1000)
        .round(3)
        .sort_values(ascending=False)
        .to_dict()
    )

    has_bbox = all(col in df.columns for col in BBOX_COLUMNS)

    gap = df[df["is_gap_edge"] & ~df["has_parallel_cycleway"] & df["name"].notna() & (df["name"] != "")]
    streets = []
    if not gap.empty:
        grouped = gap.groupby("name", sort=False)
        rows = []
        for name, group in grouped:
            top_centrality_row = group.loc[group["centrality"].idxmax()]
            row = {
                "name": name,
                "lts": int(group["lts"].max()),
                "centrality": round(float(top_centrality_row["centrality"]), 4),
                "centrality_class": top_centrality_row["centrality_class"],
                "length_km": round(float(group["length"].sum()) / 1000, 3),
                "edge_count": int(len(group)),
                "highway": group["highway"].mode().iat[0] if not group["highway"].mode().empty else None,
            }
            # The stats page's embedded map (web/stats/stats.js,
            # focusPriorityStreet) used to find a clicked street's
            # location by querying whatever vector tiles the map already
            # had loaded for the CURRENT view/zoom - which, for a street
            # not prominent enough to be included in the tiles at the
            # map's initial whole-comune zoom level (tippecanoe thins out
            # minor streets at low zoom for rendering performance), meant
            # nothing was loaded to query and the map silently didn't
            # move. Precomputing each street's bounding box here instead
            # (exact from real geometry on the parquet path; tile-bounds-
            # union - see pmtiles_edges_service.py's _tile_bounds - on the
            # pmtiles path, close enough for a fitBounds() call) sidesteps
            # that entirely: the browser never needs to query loaded
            # tiles to find out where a street is.
            if has_bbox:
                row["bbox"] = [
                    round(float(group["bbox_minlon"].min()), 5),
                    round(float(group["bbox_minlat"].min()), 5),
                    round(float(group["bbox_maxlon"].max()), 5),
                    round(float(group["bbox_maxlat"].max()), 5),
                ]
            rows.append(row)
        rows.sort(key=lambda r: (r["lts"], r["centrality"], r["length_km"]), reverse=True)
        streets = rows[:TOP_N_STREETS]

    return {"highway_km": highway_km, "streets": streets}


def build_one(parquet_path: str) -> dict:
    df = pd.read_parquet(parquet_path, columns=NEEDED_COLUMNS + ["geometry"])

    # <slug>_all_lts.parquet's geometry column is WKB in WORKING_CRS
    # (EPSG:3035, LAEA Europe metres - see domain/crs.py), the pipeline's
    # internal working projection for length/buffer maths - NOT WGS84 lon/
    # lat, unlike the sibling _all_lts.geojson (which the geojson format
    # itself requires reprojected back before export). Bounds computed
    # directly off the raw WKB would silently come out as metre offsets,
    # not degrees - reproject first. chunked_to_crs (not gdf.to_crs()
    # directly) works around a pyproj/numpy crash on large coordinate
    # counts in this environment - see that function's own docstring.
    import geopandas as gpd

    from ltsbikeplan.domain.crs import WORKING_CRS, chunked_to_crs

    gdf = gpd.GeoDataFrame(df.drop(columns=["geometry"]), geometry=gpd.GeoSeries.from_wkb(df["geometry"]), crs=WORKING_CRS)
    gdf = chunked_to_crs(gdf, "EPSG:4326")
    bounds = gdf.geometry.bounds  # columns: minx, miny, maxx, maxy
    gdf["bbox_minlon"] = bounds["minx"]
    gdf["bbox_minlat"] = bounds["miny"]
    gdf["bbox_maxlon"] = bounds["maxx"]
    gdf["bbox_maxlat"] = bounds["maxy"]

    return build_from_dataframe(pd.DataFrame(gdf.drop(columns="geometry")))


# Atomic (write-then-rename) so a job killed mid-write (low-priority
# jobs on a shared box are exactly the kind that get preempted) never
# leaves a truncated file the stats page would then fail to fetch/parse.
def write_result(out_dir: str, istat_code: str, comune: str, result: dict) -> None:
    result["istat_code"] = istat_code
    result["comune"] = comune
    out_path = os.path.join(out_dir, f"{istat_code}.json")
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w") as file_handle:
        json.dump(result, file_handle, ensure_ascii=False)
    os.replace(tmp_path, out_path)


# Unlike build_comuni_stats.py's single merged output file, this script's
# output is already one file per comune - genuinely resumable for free by
# just skipping whatever's already there. Set LTSBP_FORCE_REBUILD=1 to
# regenerate everything anyway (e.g. after a code change to the
# aggregation logic itself, where already-written files would otherwise
# look "done" despite being stale).
FORCE_REBUILD = os.environ.get("LTSBP_FORCE_REBUILD") == "1"


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    default_data_dir = os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    data_dir = sys.argv[1] if len(sys.argv) > 1 else default_data_dir
    web_data_dir = os.path.join(repo_root, "web", "data")
    out_dir = os.path.join(web_data_dir, "interventions")
    os.makedirs(out_dir, exist_ok=True)

    def already_done(istat_code: str) -> bool:
        return not FORCE_REBUILD and os.path.exists(os.path.join(out_dir, f"{istat_code}.json"))

    seen_istat_codes: set[str] = set()
    written = 0
    skipped = 0
    already = 0

    parquet_paths = sorted(glob.glob(os.path.join(data_dir, "*", "*_all_lts.parquet")))
    print(f"Processing {len(parquet_paths)} area(s) from raw data/:", flush=True)
    for parquet_path in parquet_paths:
        stats_path = parquet_path.replace("_all_lts.parquet", "_stats.json")
        if not os.path.exists(stats_path):
            skipped += 1
            continue
        with open(stats_path) as file_handle:
            stats = json.load(file_handle)
        istat_code = stats.get("istat_code")
        if not istat_code:
            skipped += 1
            continue
        seen_istat_codes.add(istat_code)
        if already_done(istat_code):
            already += 1
            continue

        result = build_one(parquet_path)
        write_result(out_dir, istat_code, stats.get("comune"), result)
        written += 1
        if written % 200 == 0:
            print(f"  {written}...", flush=True)
    print(f"  {written} written from raw data/ ({already} already up to date, {skipped} skipped)", flush=True)

    comuni_index_path = os.path.join(web_data_dir, "comuni_index.json")
    slug_to_istat = {}
    if os.path.exists(comuni_index_path):
        with open(comuni_index_path) as file_handle:
            slug_to_istat = {entry["slug"]: entry["istat"] for entry in json.load(file_handle)}

    pmtiles_paths = sorted(glob.glob(os.path.join(web_data_dir, "*_lts.pmtiles")))
    reconstructed = 0
    already_pmtiles = 0
    for path in pmtiles_paths:
        slug = os.path.basename(path)[: -len("_lts.pmtiles")]
        if slug in NON_COMUNE_PMTILES_SLUGS:
            continue
        istat_code = slug_to_istat.get(slug)
        if not istat_code or istat_code in seen_istat_codes:
            continue
        if already_done(istat_code):
            already_pmtiles += 1
            continue
        try:
            edges = load_edges_dataframe(path)
            if edges.empty:
                continue
            result = build_from_dataframe(edges)
            comune_name = edges["comune"].iloc[0] if "comune" in edges.columns else slug.replace("_", " ")
            write_result(out_dir, istat_code, comune_name, result)
            reconstructed += 1
            if reconstructed % 200 == 0:
                print(f"  {reconstructed} reconstructed from pmtiles...", flush=True)
        except Exception as error:  # noqa: BLE001 - one bad tileset shouldn't abort the whole batch
            print(f"  skip {slug} (reconstruction from pmtiles failed: {error})", file=sys.stderr, flush=True)

    total = written + reconstructed
    print(
        f"Wrote {total} intervention file(s) to {out_dir} "
        f"({written} from raw data/, {reconstructed} reconstructed from pmtiles, "
        f"{already + already_pmtiles} already up to date and skipped)",
        flush=True,
    )


if __name__ == "__main__":
    main()
