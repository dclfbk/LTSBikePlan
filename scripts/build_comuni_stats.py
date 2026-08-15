#!/usr/bin/env python3
"""Merges every processed area's <slug>_stats.json (written by
pipeline/compute_lts.py, see domain/area_statistics.py) with ISTAT
reference data - regione/provincia hierarchy and capoluogo flags
(services/istat_registry_service.py), plus superficie computed from the
already-cached comuni boundary geometry
(services/area_index_service.py::compute_comuni_superficie_km2) - into one
national file, web/data/italia_comuni_stats.json, for the comuni
comparison page (web/comuni.html).

Population/density are NOT included yet - see
services/istat_registry_service.py's module docstring for why.

Same "glob every area under data_dir, merge into one file" pattern as
scripts/build_national_tiles.sh - rerun after processing more areas.

Usage: scripts/build_comuni_stats.py [data_dir]
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.area_index_service import compute_comuni_superficie_km2
from ltsbikeplan.services.istat_registry_service import IstatRegistryService


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    default_data_dir = os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    data_dir = sys.argv[1] if len(sys.argv) > 1 else default_data_dir
    out_path = os.path.join(repo_root, "web", "data", "italia_comuni_stats.json")

    stats_paths = sorted(glob.glob(os.path.join(data_dir, "*", "*_stats.json")))
    if not stats_paths:
        print(
            f"No *_stats.json found under {data_dir} - run 'ltsbikeplan compute-lts' for at least one area first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Merging {len(stats_paths)} area(s):")
    for path in stats_paths:
        print(f"  {path}")

    registry = IstatRegistryService(cache_dir=data_dir).load()
    superficie = compute_comuni_superficie_km2(data_dir)

    merged = []
    for path in stats_paths:
        with open(path) as file_handle:
            record = json.load(file_handle)
        istat_code = record.get("istat_code") or ""
        registry_entry = registry.get(istat_code, {})
        record["regione"] = registry_entry.get("regione")
        record["provincia"] = registry_entry.get("provincia")
        record["capoluogo_provincia"] = registry_entry.get("capoluogo_provincia", False)
        record["capoluogo_regione"] = registry_entry.get("capoluogo_regione", False)
        record["superficie_km2"] = superficie.get(istat_code)
        merged.append(record)

    merged.sort(key=lambda r: r["comune"])

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as file_handle:
        json.dump(merged, file_handle, ensure_ascii=False)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
