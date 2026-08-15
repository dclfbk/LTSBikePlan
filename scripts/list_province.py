#!/usr/bin/env python3
"""Prints every Italian provincia known to osmit-estratti's index, one per
line as "name<TAB>slug" - the list scripts/build_italy_map_cron.sh iterates
over. Reuses AreaResolver's own cached index fetch (same 24h cache under
data/_cache/osmit_index/) instead of hardcoding ~107 names that would drift
out of sync with osmit-estratti's own data. Printing the slug alongside the
name avoids re-deriving it (and re-quoting names with apostrophes, e.g.
"Valle d'Aosta") inside the calling shell script.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.domain.area_spec import slugify
from ltsbikeplan.services.area_index_service import AreaResolver


def main() -> None:
    data_dir = os.environ.get(
        "LTSBP_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    )
    resolver = AreaResolver(cache_dir=data_dir)
    for feature in resolver._load_index("provincia"):
        name = feature.get("properties", {}).get("name")
        if name:
            print(f"{name}\t{slugify(name)}")


if __name__ == "__main__":
    main()
