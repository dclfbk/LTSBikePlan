#!/usr/bin/env python3
"""Incrementally patches web/data/comuni_index.json for ONE provincia,
instead of scripts/build_comuni_index.py's full from-scratch rebuild over
every comune in data/_cache/comuni_progress.tsv.

For each comune in the given provincia (by ISTAT code):
  - already indexed -> only has_routing is refreshed, to match actual
    <slug>_routing.bin presence under web/data/ (bbox/slug left alone).
    Written for exactly the gap this session found live: Palermo's
    routing.bin was copied onto the production server by hand, outside
    scripts/reprocess_comune.sh's normal fetch/compute-lts/build_tiles/
    build_routing_graph pipeline, so comuni_progress.tsv never heard
    about it and build_comuni_index.py's own full rebuild had nothing
    telling it to flip has_routing - this checks the actual file instead
    of trusting progress.tsv.
  - not indexed yet (a genuinely new comune, or one whose _lts.pmtiles
    was just built for the first time) -> a full new entry is added,
    bbox computed the same way build_comuni_index.py does (the real
    boundary polygon AreaResolver already caches, not a guess from the
    pmtiles header).

Everything outside the given provincia is left untouched - this never
scans all ~7900 comuni the way build_comuni_index.py does, so it's cheap
to run right after reprocessing (or hand-copying) just one provincia's
files instead of paying for a whole-Italy rebuild.

Usage: python3 scripts/patch_comuni_index.py <prov_istat_code> [data_dir]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

import geopandas as gpd

from ltsbikeplan.services.area_index_service import AreaResolver


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print(f"usage: {sys.argv[0]} <prov_istat_code> [data_dir]", file=sys.stderr)
        sys.exit(1)
    prov_istat_code = sys.argv[1]

    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    default_data_dir = os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    data_dir = sys.argv[2] if len(sys.argv) > 2 else default_data_dir
    web_data_dir = os.path.join(repo_root, "web", "data")
    index_path = os.path.join(web_data_dir, "comuni_index.json")

    resolver = AreaResolver(data_dir)

    comuni = [
        feature["properties"]
        for feature in resolver._load_index("comune")  # noqa: SLF001 - see module docstring
        if feature.get("properties", {}).get("prov_istat_code") == prov_istat_code
    ]
    if not comuni:
        print(f"ERROR: no comune found with prov_istat_code={prov_istat_code!r}", file=sys.stderr)
        sys.exit(1)
    print(f"{len(comuni)} comuni in provincia {prov_istat_code}.")

    entries = []
    if os.path.exists(index_path):
        with open(index_path) as file_handle:
            entries = json.load(file_handle)
    entry_by_istat = {entry["istat"]: entry for entry in entries}

    gdf = None  # only loaded (and only once) if a genuinely new comune needs a bbox
    added, updated = 0, 0
    for props in comuni:
        istat = props["istat"]
        slug = resolver._slug_for("comune", props)  # noqa: SLF001
        has_routing = os.path.exists(os.path.join(web_data_dir, f"{slug}_routing.bin"))

        existing = entry_by_istat.get(istat)
        if existing is not None:
            if existing.get("has_routing") != has_routing:
                existing["has_routing"] = has_routing
                updated += 1
            continue

        if not os.path.exists(os.path.join(web_data_dir, f"{slug}_lts.pmtiles")):
            continue  # not built at all yet - nothing to index

        if gdf is None:
            boundary_path = resolver.ensure_cached("comune")
            gdf = gpd.read_file(boundary_path).set_crs("EPSG:4326")
        row = gdf[gdf["istat"] == istat]
        if row.empty:
            print(f"WARNING: no boundary geometry for {slug} (istat={istat}) - skipping", file=sys.stderr)
            continue
        minx, miny, maxx, maxy = row.iloc[0].geometry.bounds
        new_entry = {
            "istat": istat,
            "slug": slug,
            "bbox": [round(minx, 5), round(miny, 5), round(maxx, 5), round(maxy, 5)],
            "has_routing": has_routing,
        }
        entries.append(new_entry)
        entry_by_istat[istat] = new_entry
        added += 1

    entries.sort(key=lambda e: e["istat"])
    os.makedirs(web_data_dir, exist_ok=True)
    with open(index_path, "w") as file_handle:
        json.dump(entries, file_handle, ensure_ascii=False)

    print(f"Wrote {index_path}: {added} comuni added, {updated} had has_routing flipped.")


if __name__ == "__main__":
    main()
