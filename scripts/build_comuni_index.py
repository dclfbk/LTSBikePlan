#!/usr/bin/env python3
"""Builds web/data/comuni_index.json: [{istat, slug, bbox, has_routing}, ...]
for every comune that already has a <slug>_lts.pmtiles built - the lookup
web/app.js uses at zoom >= COMUNE_SWAP_MIN_ZOOM to decide which per-comune
pmtiles to add as sources once italia_lts.pmtiles (capped at maxzoom 11, see
build_national_tiles.sh) runs out of detail. web/routing.js also reads this
list (regardless of current zoom) to find which comuni's <slug>_routing.json
to fetch for a given start/end pair - see has_routing below.

istat->slug comes from data/_cache/comuni_progress.tsv, but that file only
records fetch+compute-lts success - build_tiles.sh's own tile build can fail
independently and progress.tsv still gets a line written either way (see
build_italy_map_comuni_cron.sh's process_comune), so actual <slug>_lts.pmtiles
presence under web/data/ is the real gate, checked here explicitly.

bbox comes from the same osmit-estratti comuni boundary topojson
AreaResolver already downloads/caches for name/ISTAT resolution - GDAL's
topojson driver decodes real polygon geometry via geopandas.read_file, same
approach already used by services/area_index_service.py's
compute_comuni_superficie_km2. A plain bbox (not the real polygon) is enough
for app.js's viewport-intersection check - cheap client-side and precise
enough for Italy's mostly-compact comuni; the cost is only ever an
occasional extra pmtiles fetched near a comune's corner, never wrong data.

Usage: scripts/build_comuni_index.py [data_dir]
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

import geopandas as gpd

from ltsbikeplan.services.area_index_service import AreaResolver


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    default_data_dir = os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    data_dir = sys.argv[1] if len(sys.argv) > 1 else default_data_dir
    web_data_dir = os.path.join(repo_root, "web", "data")
    progress_path = os.path.join(data_dir, "_cache", "comuni_progress.tsv")
    out_path = os.path.join(web_data_dir, "comuni_index.json")

    if not os.path.exists(progress_path):
        print(
            f"No {progress_path} - run scripts/build_italy_map_comuni_cron.sh for at least one comune first.",
            file=sys.stderr,
        )
        sys.exit(1)

    slug_by_istat = {}
    with open(progress_path, newline="") as file_handle:
        for row in csv.reader(file_handle, delimiter="\t"):
            istat, slug, _timestamp = row
            slug_by_istat[istat] = slug

    built_slug_by_istat = {
        istat: slug
        for istat, slug in slug_by_istat.items()
        if os.path.exists(os.path.join(web_data_dir, f"{slug}_lts.pmtiles"))
    }
    print(f"{len(built_slug_by_istat)}/{len(slug_by_istat)} comuni in progress.tsv have a built pmtiles.")

    resolver = AreaResolver(data_dir)
    boundary_path = resolver.ensure_cached("comune")
    gdf = gpd.read_file(boundary_path).set_crs("EPSG:4326")

    entries = []
    for _, row in gdf.iterrows():
        slug = built_slug_by_istat.get(row["istat"])
        if slug is None:
            continue
        minx, miny, maxx, maxy = row.geometry.bounds
        has_routing = os.path.exists(os.path.join(web_data_dir, f"{slug}_routing.json"))
        entries.append(
            {
                "istat": row["istat"],
                "slug": slug,
                "bbox": [round(minx, 5), round(miny, 5), round(maxx, 5), round(maxy, 5)],
                "has_routing": has_routing,
            }
        )

    entries.sort(key=lambda e: e["istat"])

    os.makedirs(web_data_dir, exist_ok=True)
    with open(out_path, "w") as file_handle:
        json.dump(entries, file_handle, ensure_ascii=False)

    print(f"Wrote {out_path} ({len(entries)} comuni)")


if __name__ == "__main__":
    main()
