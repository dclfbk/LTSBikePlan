#!/usr/bin/env python3
"""Populates data/_cache/comuni_progress.tsv from whatever web/data/
<slug>_lts.pmtiles + <slug>_routing.bin files already exist on disk -
for switching to scripts/reprocess_italia_low_resource.sh's --resume (or
picking build_italy_map_comuni_cron.sh back up) AFTER a batch of comuni
was already processed by something that never wrote to that progress
file (e.g. calcola.sh's own `xargs -P 10 ... reprocess_comune.sh` loop -
reprocess_comune.sh itself doesn't touch comuni_progress.tsv, only
build_italy_map_comuni_cron.sh's own loop does).

Without this, --resume has nothing to skip and redoes every comune from
scratch even though hundreds of them are already sitting in web/data/
with today's code's numbers.

Uses each pmtiles file's own mtime as the recorded timestamp (real work
already done, not "now") - doesn't overwrite an istat already present in
the progress file (first-seen timestamp wins, same append-only semantics
build_italy_map_comuni_cron.sh's own loop relies on).

Usage: PYTHONPATH=code python3 scripts/backfill_comuni_progress.py [data_dir]
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.area_index_service import AreaResolver


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LTSBP_DATA_DIR", os.path.join(repo_root, "data"))
    web_data_dir = os.path.join(repo_root, "web", "data")
    progress_path = os.path.join(data_dir, "_cache", "comuni_progress.tsv")

    already = set()
    if os.path.exists(progress_path):
        with open(progress_path) as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if parts and parts[0]:
                    already.add(parts[0])
    print(f"{len(already)} comuni already recorded in {progress_path}.")

    resolver = AreaResolver(cache_dir=data_dir)
    comuni = resolver.list_areas("comune")
    print(f"{len(comuni)} comuni known to osmit-estratti's index.")

    os.makedirs(os.path.dirname(progress_path), exist_ok=True)
    added = 0
    with open(progress_path, "a") as out:
        for area in comuni:
            istat = area["istat"]
            slug = area["slug"]
            if istat in already:
                continue
            pmtiles = os.path.join(web_data_dir, f"{slug}_lts.pmtiles")
            routing_bin = os.path.join(web_data_dir, f"{slug}_routing.bin")
            if not (os.path.exists(pmtiles) and os.path.exists(routing_bin)):
                continue
            ts = datetime.fromtimestamp(os.path.getmtime(pmtiles), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            out.write(f"{istat}\t{slug}\t{ts}\n")
            already.add(istat)
            added += 1

    print(f"Added {added} comuni to {progress_path} (now {len(already)} total).")


if __name__ == "__main__":
    main()
