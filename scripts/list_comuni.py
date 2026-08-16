#!/usr/bin/env python3
"""Prints every Italian comune known to osmit-estratti's index, one per line
as "istat<TAB>name<TAB>slug" - the list scripts/build_italy_map_comuni_cron.sh
iterates over incrementally. Reuses AreaResolver's own cached index fetch
(same 24h cache under data/_cache/osmit_index/) instead of scraping
osmit-estratti's site for a comuni list - the topojson index it already
downloads for name/ISTAT resolution covers all ~7900 comuni just as it does
for province.

istat comes first (unlike list_province.py's plain "name<TAB>slug"): at
comune scale a handful of names collide (e.g. two comuni are both named
"Paterno" - AreaResolver.list_areas already disambiguates their slugs with
an istat suffix, but the *cron loop* needs istat too, to resolve each
comune via --istat instead of an ambiguous --area name match, and to key
its per-comune progress file.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.area_index_service import AreaResolver


def main() -> None:
    data_dir = os.environ.get(
        "LTSBP_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    )
    resolver = AreaResolver(cache_dir=data_dir)
    for area in resolver.list_areas("comune"):
        print(f"{area['istat']}\t{area['name']}\t{area['slug']}")


if __name__ == "__main__":
    main()
