#!/usr/bin/env python3
"""Deletes one area's cached .osm.pbf extract and mosaiced DEM GeoTIFF -
the two large per-area downloads services/osm_pbf_service.py and
pipeline/fetch.py cache permanently under data/_cache/ with no expiry of
their own (see download_pbf_extract/_resolve_dem_path: both just check
`os.path.exists` and reuse forever). Fine for a single-area workflow, but
scripts/build_italy_map_cron.sh runs this over every Italian provincia -
left unmanaged, that's ~107 permanently-retained .osm.pbf files (tens to
low hundreds of MB each) plus their DEM mosaics.

Deliberately leaves data/_cache/mapterhorn_tiles/ (the raw DEM tile cache)
alone: those tiles are shared/reused across adjacent province, so pruning
them per-area would mostly just make neighbouring province re-download
tiles they'd otherwise still have cached, for little disk-space benefit
compared to the two big per-area files this script does remove.

Usage: PYTHONPATH=code python3 scripts/cleanup_area_cache.py <area> [--area-level LEVEL] [--istat CODE] [data_dir]
Mirrors the same --area/--area-level/--istat resolution `ltsbikeplan
fetch`/`compute-lts --osmit-estratti` use, so it targets the exact same
cache files those commands populated for the same area.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.area_index_service import AreaResolver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("area")
    parser.add_argument("--area-level", default="provincia", choices=["comune", "provincia", "regione"])
    parser.add_argument("--istat", default=None)
    parser.add_argument(
        "data_dir",
        nargs="?",
        default=os.environ.get(
            "LTSBP_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        ),
    )
    args = parser.parse_args()

    resolver = AreaResolver(cache_dir=args.data_dir)
    area = resolver.resolve(args.area, level=args.area_level, istat=args.istat)

    key = area.istat_code or area.slug
    pbf_path = os.path.join(args.data_dir, "_cache", "osm_pbf", f"{key}.osm.pbf")
    dem_path = os.path.join(args.data_dir, "_cache", "dem", f"{area.slug}_mapterhorn.tif")

    freed_bytes = 0
    for path in (pbf_path, dem_path):
        if os.path.exists(path):
            freed_bytes += os.path.getsize(path)
            os.remove(path)
            print(f"Removed {path}")
        else:
            print(f"Not cached (nothing to remove): {path}")

    print(f"Freed {freed_bytes / (1024 * 1024):.1f} MB for {area.name!r} ({key}).")


if __name__ == "__main__":
    main()
