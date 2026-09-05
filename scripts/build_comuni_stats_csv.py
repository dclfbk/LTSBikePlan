#!/usr/bin/env python3
"""Exports web/data/italia_comuni_stats.json as a downloadable CSV, for
the stats page's own "Scarica il dataset completo" button
(web/stats/index.html) - so the same numbers shown as charts/tables can
be opened in a spreadsheet or reused elsewhere, under the same ODbL
terms as the rest of the site (the data is entirely derived from
OpenStreetMap's own road characteristics, see that button's own license
note).

Flattens km_by_lts (a nested {lts_class: km} dict in the JSON, keys
"0".."4") into one column per class, km_lts_0..km_lts_4 - CSV has no
nested structure.

Always zipped, not conditionally on a size check: the flattened CSV is
one row per comune (~7900) with ~20 columns, several MB uncompressed for
the full national dataset, and this kind of repetitive numeric/text
table compresses well - there's no realistic case where serving the
raw .csv instead would be better.

Usage: scripts/build_comuni_stats_csv.py
"""
from __future__ import annotations

import csv
import io
import json
import os
import zipfile

LTS_CLASSES = ["0", "1", "2", "3", "4"]

# Identity/geography first, then the metrics a reader is most likely
# after, flattened km_by_lts last (the one field that isn't a single
# already-named column in the source JSON) - so the "important" columns
# read left-to-right first in a spreadsheet without scrolling.
FIELD_ORDER = [
    "istat_code",
    "comune",
    "provincia",
    "regione",
    "capoluogo_provincia",
    "capoluogo_regione",
    "popolazione",
    "superficie_km2",
    "total_km",
    "low_stress_km",
    "high_stress_km",
    "low_stress_share",
    "separated_path_km",
    "priority_intervention_km",
    "low_stress_island_count",
    "low_stress_island_km",
    "excluded_motorroad_km",
    "excluded_mountain_trail_km",
    "excluded_restricted_access_km",
    "excluded_service_road_km",
] + [f"km_lts_{cls}" for cls in LTS_CLASSES]


def _flatten(record: dict) -> dict:
    flat = {field: record.get(field) for field in FIELD_ORDER}
    km_by_lts = record.get("km_by_lts") or {}
    for cls in LTS_CLASSES:
        flat[f"km_lts_{cls}"] = km_by_lts.get(cls)
    return flat


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    in_path = os.path.join(repo_root, "web", "data", "italia_comuni_stats.json")
    out_path = os.path.join(repo_root, "web", "data", "italia_comuni_stats.csv.zip")

    with open(in_path) as file_handle:
        comuni = json.load(file_handle)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELD_ORDER)
    writer.writeheader()
    for record in sorted(comuni, key=lambda r: r["comune"]):
        writer.writerow(_flatten(record))
    csv_bytes = buffer.getvalue().encode("utf-8")

    # Write-then-rename (same atomicity convention as
    # build_comuni_stats.py's own _write_output) so a concurrent
    # download never sees a truncated zip mid-write.
    tmp_path = out_path + ".tmp"
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        zip_file.writestr("italia_comuni_stats.csv", csv_bytes)
    os.replace(tmp_path, out_path)

    print(f"Wrote {out_path} ({len(comuni)} comuni, {len(csv_bytes):,} bytes csv -> {os.path.getsize(out_path):,} bytes zipped)")


if __name__ == "__main__":
    main()
