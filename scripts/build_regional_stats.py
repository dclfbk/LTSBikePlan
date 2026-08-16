#!/usr/bin/env python3
"""Rolls up web/data/italia_comuni_stats.json (per-comune, written by
scripts/build_comuni_stats.py) into per-provincia and per-regione totals -
web/data/italia_provincia_stats.json and web/data/italia_regione_stats.json.

Pure aggregation over data already collected, no new fetching/processing:
every comune's istat_code maps to exactly one provincia and one regione
(services/istat_registry_service.py), so summing already-computed per-
comune indicators upward is correct. Going the other way - deriving comuni
totals from a provincia-level compute-lts run - is NOT possible: every edge
of a processed area is tagged with that area's own name/istat as a
constant (pipeline/compute_lts.py), not via a per-edge spatial join to the
smaller units inside it.

Extensive fields (km, counts, superficie) are summed. low_stress_share is
NOT averaged across comuni (that would weight a tiny comune the same as a
big city) - it's re-derived from the summed low_stress_km/high_stress_km,
the same formula domain/area_statistics.py uses per comune.

The comuni pipeline is incremental (scripts/build_italy_map_comuni_cron.sh
processes a batch at a time, not all ~7893 comuni in one run), so every
rollup row also reports comuni_processed/comuni_total/coverage_pct against
the full ISTAT registry - read a provincia/regione's numbers as "partial,
N of M comuni so far" until coverage_pct reaches 100.

Usage: scripts/build_regional_stats.py [data_dir]
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.istat_registry_service import IstatRegistryService

_SUM_FIELDS = [
    "total_km",
    "low_stress_km",
    "high_stress_km",
    "separated_path_km",
    "priority_intervention_km",
    "low_stress_island_km",
    "excluded_motorroad_km",
    "excluded_mountain_trail_km",
    "superficie_km2",
]
_KM_BY_LTS_CLASSES = ["0", "1", "2", "3", "4"]


def _new_bucket() -> dict:
    return {
        "sums": {field: 0.0 for field in _SUM_FIELDS},
        "km_by_lts": {cls: 0.0 for cls in _KM_BY_LTS_CLASSES},
        "low_stress_island_count": 0,
        "comuni_processed": 0,
    }


def _add(bucket: dict, record: dict) -> None:
    for field in _SUM_FIELDS:
        value = record.get(field)
        if value is not None:
            bucket["sums"][field] += value
    for cls in _KM_BY_LTS_CLASSES:
        bucket["km_by_lts"][cls] += (record.get("km_by_lts") or {}).get(cls, 0.0)
    bucket["low_stress_island_count"] += record.get("low_stress_island_count") or 0
    bucket["comuni_processed"] += 1


def _finalize(name: str, bucket: dict, total_comuni: int) -> dict:
    low = bucket["sums"]["low_stress_km"]
    high = bucket["sums"]["high_stress_km"]
    classified = low + high
    processed = bucket["comuni_processed"]
    return {
        "area": name,
        **{field: round(value, 3) for field, value in bucket["sums"].items()},
        "km_by_lts": {cls: round(value, 3) for cls, value in bucket["km_by_lts"].items()},
        "low_stress_share": round(low / classified, 4) if classified else None,
        "low_stress_island_count": bucket["low_stress_island_count"],
        "comuni_processed": processed,
        "comuni_total": total_comuni,
        "coverage_pct": round(100 * processed / total_comuni, 1) if total_comuni else None,
    }


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    default_data_dir = os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    data_dir = sys.argv[1] if len(sys.argv) > 1 else default_data_dir

    comuni_path = os.path.join(repo_root, "web", "data", "italia_comuni_stats.json")
    if not os.path.exists(comuni_path):
        print(f"Missing {comuni_path} - run scripts/build_comuni_stats.py first.", file=sys.stderr)
        sys.exit(1)

    with open(comuni_path) as file_handle:
        comuni = json.load(file_handle)

    registry = IstatRegistryService(cache_dir=data_dir).load()
    total_per_provincia: dict = defaultdict(int)
    total_per_regione: dict = defaultdict(int)
    for entry in registry.values():
        total_per_provincia[entry["provincia"]] += 1
        total_per_regione[entry["regione"]] += 1

    provincia_buckets: dict = defaultdict(_new_bucket)
    regione_buckets: dict = defaultdict(_new_bucket)
    skipped = 0
    for record in comuni:
        provincia = record.get("provincia")
        regione = record.get("regione")
        if not provincia or not regione:
            skipped += 1
            continue
        _add(provincia_buckets[provincia], record)
        _add(regione_buckets[regione], record)

    if skipped:
        print(
            f"Skipped {skipped} comune record(s) missing provincia/regione (not found in the ISTAT registry).",
            file=sys.stderr,
        )

    provincia_out = [
        _finalize(name, bucket, total_per_provincia.get(name, 0)) for name, bucket in provincia_buckets.items()
    ]
    regione_out = [_finalize(name, bucket, total_per_regione.get(name, 0)) for name, bucket in regione_buckets.items()]
    provincia_out.sort(key=lambda r: r["area"])
    regione_out.sort(key=lambda r: r["area"])

    provincia_path = os.path.join(repo_root, "web", "data", "italia_provincia_stats.json")
    regione_path = os.path.join(repo_root, "web", "data", "italia_regione_stats.json")
    with open(provincia_path, "w") as file_handle:
        json.dump(provincia_out, file_handle, ensure_ascii=False)
    with open(regione_path, "w") as file_handle:
        json.dump(regione_out, file_handle, ensure_ascii=False)

    print(f"Wrote {provincia_path} ({len(provincia_out)} province)")
    print(f"Wrote {regione_path} ({len(regione_out)} regioni)")


if __name__ == "__main__":
    main()
