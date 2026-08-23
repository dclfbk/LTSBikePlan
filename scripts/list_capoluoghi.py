#!/usr/bin/env python3
"""Prints every Italian comune that's a capoluogo di provincia, città
metropolitana, or libero consorzio (Sicily's post-2015 provincia
equivalent) - ISTAT lumps all three into one flag, "Flag Comune capoluogo
di Provincia/Città metropolitana/libero consorzio" (see
services/istat_registry_service.py::IstatRegistryService), so that one
flag is the exact union scripts/build_capoluoghi_tiles.sh needs. ~107
comuni out of ~7893, one per line as "istat<TAB>name<TAB>slug" - same
format as scripts/list_comuni.py (which lists all ~7893), reusing
AreaResolver's own cached osmit-estratti index for the name/slug half and
IstatRegistryService's cached ISTAT registry for the flag itself, rather
than hand-maintaining a list that would go stale at the next province
reform.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.area_index_service import AreaResolver
from ltsbikeplan.services.istat_registry_service import IstatRegistryService


def main() -> None:
    data_dir = os.environ.get(
        "LTSBP_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    )
    registry = IstatRegistryService(cache_dir=data_dir).load()
    resolver = AreaResolver(cache_dir=data_dir)
    for area in resolver.list_areas("comune"):
        istat = area["istat"]
        if istat and registry.get(istat, {}).get("capoluogo_provincia"):
            print(f"{istat}\t{area['name']}\t{area['slug']}")


if __name__ == "__main__":
    main()
