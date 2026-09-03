#!/usr/bin/env python3
"""Merges every processed area's stats with ISTAT reference data -
regione/provincia hierarchy and capoluogo flags
(services/istat_registry_service.py), superficie computed from the
already-cached comuni boundary geometry
(services/area_index_service.py::compute_comuni_superficie_km2), and
resident population (services/population_service.py) - into one national
file, web/data/italia_comuni_stats.json, for the comuni comparison page
(web/comuni.html) and the stats page (web/stats/).

Two sources for the per-comune stats themselves, preferred in this order:
1. data/<slug>/<slug>_stats.json, written by pipeline/compute_lts.py
   (domain/area_statistics.py) from the full raw export - the fast path,
   no reconstruction needed.
2. web/data/<slug>_lts.pmtiles, for any comune whose raw data/<slug>/
   folder is gone (deleted to reclaim disk once its tileset was already
   built - the pmtiles alone are enough to keep serving the map). Read
   back via services/pmtiles_edges_service.py and fed through the exact
   same compute_area_statistics() the raw path uses - see that module's
   own docstring for why this is lossless, not an approximation.

Same "glob every area, merge into one file" pattern as
scripts/build_national_tiles.sh - rerun after processing more areas.

Usage: scripts/build_comuni_stats.py [data_dir]
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.domain.area_statistics import compute_area_statistics
from ltsbikeplan.services.area_index_service import compute_comuni_superficie_km2
from ltsbikeplan.services.istat_registry_service import IstatRegistryService, normalize_comune_name
from ltsbikeplan.services.pmtiles_edges_service import load_edges_dataframe
from ltsbikeplan.services.population_service import PopulationService

# Not a comune - the merged whole-country low-detail tileset
# (scripts/build_national_tiles.sh). Matches the *_lts.pmtiles glob below
# but has no single istat_code/comune to attribute stats to.
NON_COMUNE_PMTILES_SLUGS = {"italia"}


CHECKPOINT_EVERY = 200


def _registry_lookup(istat_code: str, comune_name: str, registry: dict, registry_by_name: dict) -> dict:
    entry = registry.get(istat_code)
    if entry:
        return entry
    # Falls back to matching by name when the istat_code itself isn't in
    # the CURRENT registry - not a data error, just an old istat_code:
    # Sardegna's repeated provincial reorganizations renumbered nearly
    # every comune there, so already-processed data (some of it years
    # old) can carry a legacy code the live ISTAT download no longer
    # recognizes, even though the comune itself and its name are
    # unchanged. See IstatRegistryService.load_by_name's own docstring
    # (confirmed 2026-09: 374/374 otherwise-orphaned comuni, effectively
    # all of Sardegna, matched this way with zero residual misses).
    # `comune_name` can carry a "Sardo/Italiano" dual name (as tagged in
    # this project's own OSM extraction) - try the full string first,
    # then each half.
    for candidate in [comune_name, *comune_name.split("/")]:
        entry = registry_by_name.get(normalize_comune_name(candidate))
        if entry:
            return entry
    return {}


def _apply_registry_fields(
    record: dict, istat_code: str, comune_name: str, registry: dict, registry_by_name: dict, superficie: dict, population: dict
) -> None:
    registry_entry = _registry_lookup(istat_code, comune_name, registry, registry_by_name)
    record["regione"] = registry_entry.get("regione")
    record["provincia"] = registry_entry.get("provincia")
    record["capoluogo_provincia"] = registry_entry.get("capoluogo_provincia", False)
    record["capoluogo_regione"] = registry_entry.get("capoluogo_regione", False)
    record["superficie_km2"] = superficie.get(istat_code)
    record["popolazione"] = population.get(istat_code)


# Atomic (write-then-rename, same filesystem) so a process killed mid-run
# - low-priority/nice'd jobs on a shared box are exactly the kind that get
# preempted or OOM-killed - never leaves the live, nginx-served JSON
# truncated or half-written. Called both mid-run (checkpoints, see
# CHECKPOINT_EVERY below) and at the very end, so an interrupted run's
# last checkpoint is always a complete, valid file - just not the FULL
# result, rather than nothing at all.
def _write_output(merged: list, out_path: str) -> None:
    ordered = sorted(merged, key=lambda r: r["comune"])
    tmp_path = out_path + ".tmp"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(tmp_path, "w") as file_handle:
        json.dump(ordered, file_handle, ensure_ascii=False)
    os.replace(tmp_path, out_path)


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    default_data_dir = os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    data_dir = sys.argv[1] if len(sys.argv) > 1 else default_data_dir
    web_data_dir = os.path.join(repo_root, "web", "data")
    out_path = os.path.join(web_data_dir, "italia_comuni_stats.json")

    istat_service = IstatRegistryService(cache_dir=data_dir)
    registry = istat_service.load()
    registry_by_name = istat_service.load_by_name()
    superficie = compute_comuni_superficie_km2(data_dir)
    population = PopulationService(cache_dir=data_dir).load()

    merged = []
    seen_istat_codes: set[str] = set()

    stats_paths = sorted(glob.glob(os.path.join(data_dir, "*", "*_stats.json")))
    print(f"Merging {len(stats_paths)} area(s) from raw data/:", flush=True)
    for path in stats_paths:
        with open(path) as file_handle:
            record = json.load(file_handle)
        istat_code = record.get("istat_code") or ""
        _apply_registry_fields(record, istat_code, record.get("comune", ""), registry, registry_by_name, superficie, population)
        merged.append(record)
        seen_istat_codes.add(istat_code)
    print(f"  {len(merged)} loaded", flush=True)

    comuni_index_path = os.path.join(web_data_dir, "comuni_index.json")
    slug_to_istat = {}
    if os.path.exists(comuni_index_path):
        with open(comuni_index_path) as file_handle:
            slug_to_istat = {entry["slug"]: entry["istat"] for entry in json.load(file_handle)}

    pmtiles_paths = sorted(glob.glob(os.path.join(web_data_dir, "*_lts.pmtiles")))
    to_reconstruct = [
        (path, os.path.basename(path)[: -len("_lts.pmtiles")]) for path in pmtiles_paths
    ]
    to_reconstruct = [
        (path, slug, slug_to_istat.get(slug))
        for path, slug in to_reconstruct
        if slug not in NON_COMUNE_PMTILES_SLUGS
    ]
    to_reconstruct = [
        (path, slug, istat_code)
        for path, slug, istat_code in to_reconstruct
        if istat_code and istat_code not in seen_istat_codes
    ]
    print(f"Reconstructing {len(to_reconstruct)} area(s) from web/data/*_lts.pmtiles (no raw data/ folder)...", flush=True)

    reconstructed = 0
    for path, slug, istat_code in to_reconstruct:
        try:
            edges = load_edges_dataframe(path)
            if edges.empty:
                continue
            record = compute_area_statistics(edges, slug)
            record["comune"] = edges["comune"].iloc[0] if "comune" in edges.columns else slug.replace("_", " ")
            record["istat_code"] = istat_code
            _apply_registry_fields(record, istat_code, record["comune"], registry, registry_by_name, superficie, population)
            merged.append(record)
            seen_istat_codes.add(istat_code)
            reconstructed += 1
        except Exception as error:  # noqa: BLE001 - one bad tileset shouldn't abort the whole national merge
            print(f"  skip {slug} (reconstruction from pmtiles failed: {error})", file=sys.stderr, flush=True)

        # Checkpoint every CHECKPOINT_EVERY comuni (not every one - the
        # write itself, plus the sort, has a cost not worth paying per
        # comune) so a low-priority job on a shared box that gets
        # preempted/killed partway through still leaves the live JSON
        # updated with most of its progress, not reverted to nothing.
        if reconstructed and reconstructed % CHECKPOINT_EVERY == 0:
            _write_output(merged, out_path)
            print(f"  {reconstructed}/{len(to_reconstruct)} reconstructed, checkpoint written", flush=True)

    if not merged:
        print("No comuni found via raw data/ or web/data/*_lts.pmtiles - nothing to merge.", file=sys.stderr)
        sys.exit(1)

    _write_output(merged, out_path)
    print(f"Wrote {out_path} ({len(merged)} comuni total, {reconstructed} reconstructed from pmtiles)", flush=True)


if __name__ == "__main__":
    main()
