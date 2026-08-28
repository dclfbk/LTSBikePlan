#!/usr/bin/env python3
"""Prints every comune under one provincia - same istat<TAB>name<TAB>slug
format as list_comuni.py (see that script), filtered to a single provincia
by ISTAT code.

scripts/list_comuni.py/AreaResolver.list_areas() don't expose prov_istat_code
(they only ever needed istat/name/slug for the whole-Italy cron loop) - this
reads the same cached osmit-estratti municipality index directly instead,
via AreaResolver's own _load_index()/_slug_for(), to get at that field
without duplicating the slugify/duplicate-name-disambiguation logic.

Usage: python3 scripts/list_comuni_for_provincia.py <prov_istat_code>
Example (Bolzano - Bozen / Alto Adige): python3 scripts/list_comuni_for_provincia.py 021

Find a provincia's ISTAT code by name:
  python3 -c "
  import json
  d = json.load(open('data/_cache/osmit_index/limits_IT_provinces.json'))
  for g in d['objects'][list(d['objects'])[0]]['geometries']:
      if 'bolzano' in g['properties']['name'].lower():
          print(g['properties'])
  "
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

from ltsbikeplan.services.area_index_service import AreaResolver


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <prov_istat_code>", file=sys.stderr)
        sys.exit(1)
    prov_istat_code = sys.argv[1]

    data_dir = os.environ.get(
        "LTSBP_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    )
    resolver = AreaResolver(cache_dir=data_dir)
    found = False
    for feature in resolver._load_index("comune"):  # noqa: SLF001 - see module docstring
        props = feature.get("properties", {})
        if props.get("prov_istat_code") != prov_istat_code:
            continue
        name = props.get("name")
        if not name:
            continue
        found = True
        slug = resolver._slug_for("comune", props)  # noqa: SLF001
        print(f"{props.get('istat')}\t{name}\t{slug}")

    if not found:
        print(f"ERROR: no comune found with prov_istat_code={prov_istat_code!r}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
