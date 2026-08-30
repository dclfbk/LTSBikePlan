#!/usr/bin/env python3
"""Flips `has_routing` to true in web/data/comuni_index.json for every
comune whose web/data/ files actually have BOTH a `<slug>_routing.bin`
AND a `<slug>_lts.pmtiles` - driven by scanning the files directly, not
by comuni_progress.tsv or a boundary-polygon lookup.

Narrower than scripts/patch_comuni_index.py on purpose: that script
covers one provincia at a time, computes a real bbox for a genuinely NEW
comune (via AreaResolver's boundary polygon), and treats `has_routing`
as true whenever `_routing.bin` alone exists. This script is a plain,
whole-`web/data/`, no-provincia-argument sweep for the narrower question
"does this comune have a WORKING pair of routing+tileset files" - it
requires .pmtiles too (not just .bin) since a comune that failed partway
through scripts/build_tiles.sh (or reprocess_comune.sh, or the cron)
after its routing.bin was already written would otherwise get flagged
routable with no tileset to actually show the route against. It only
ever sets has_routing TRUE, never back to false, and only for comuni
ALREADY present in comuni_index.json - a routing.bin/pmtiles pair for a
comune with no index entry at all (a genuinely new comune) needs
patch_comuni_index.py or build_comuni_index.py instead, since adding one
requires a real bbox this script has no way to compute.

Only touches web/data/ - unlike its sibling scripts, it has no `data_dir`
argument, since it never reads anything under data/_cache/ (no boundary
polygons, no comuni_progress.tsv).

Usage: python3 scripts/refresh_routing_status.py
"""
from __future__ import annotations

import glob
import json
import os
import sys


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    web_data_dir = os.path.join(repo_root, "web", "data")
    index_path = os.path.join(web_data_dir, "comuni_index.json")

    if not os.path.exists(index_path):
        print(f"ERROR: {index_path} not found - run build_comuni_index.py first.", file=sys.stderr)
        sys.exit(1)
    with open(index_path) as file_handle:
        entries = json.load(file_handle)
    entry_by_slug = {entry["slug"]: entry for entry in entries}

    routing_bin_paths = glob.glob(os.path.join(web_data_dir, "*_routing.bin"))
    updated, already_true, no_pmtiles, not_indexed = 0, 0, [], []
    for bin_path in routing_bin_paths:
        slug = os.path.basename(bin_path)[: -len("_routing.bin")]
        pmtiles_path = os.path.join(web_data_dir, f"{slug}_lts.pmtiles")

        entry = entry_by_slug.get(slug)
        if entry is None:
            not_indexed.append(slug)
            continue
        if not os.path.exists(pmtiles_path):
            no_pmtiles.append(slug)
            continue
        if entry.get("has_routing") is True:
            already_true += 1
            continue
        entry["has_routing"] = True
        updated += 1

    with open(index_path, "w") as file_handle:
        json.dump(entries, file_handle, ensure_ascii=False)

    print(f"Wrote {index_path}: {updated} flipped to has_routing=true, {already_true} already true.")
    if no_pmtiles:
        print(f"{len(no_pmtiles)} comune(s) have routing.bin but no matching .pmtiles yet (left untouched): {', '.join(sorted(no_pmtiles))}")
    if not_indexed:
        print(
            f"{len(not_indexed)} comune(s) have routing.bin but no comuni_index.json entry at all "
            f"(not this script's job - use patch_comuni_index.py or build_comuni_index.py): {', '.join(sorted(not_indexed))}"
        )


if __name__ == "__main__":
    main()
