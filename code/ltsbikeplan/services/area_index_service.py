from __future__ import annotations

import json
import os
import time
from typing import Optional

import requests

from ltsbikeplan.domain.area_spec import AreaLevel, AreaSpec, slugify

OSMIT_ESTRATTI_BASE = "https://osmit-estratti.wmcloud.org/output"

_INDEX_FILES = {
    "regione": ("limits_IT_regions.json", "limits_IT_regions"),
    "provincia": ("limits_IT_provinces.json", "limits_IT_provinces"),
    "comune": ("limits_IT_municipalities.json", "limits_IT_municipalities"),
}

_INDEX_CACHE_MAX_AGE_SECONDS = 24 * 3600


class AreaNotFoundError(Exception):
    pass


class AmbiguousAreaError(Exception):
    def __init__(self, query: str, matches: list):
        self.query = query
        self.matches = matches
        names = ", ".join(f"{m['name']} ({level})" for level, m in matches)
        super().__init__(f"Multiple areas match '{query}': {names}. Narrow with --area-level or --istat.")


class AreaResolver:
    """Resolves a region/province/comune name or ISTAT code to an AreaSpec
    backed by the osmit-estratti (Wikimedia Italia) pre-clipped OSM extracts.
    """

    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.join(cache_dir, "_cache", "osmit_index")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _index_path(self, level: str) -> str:
        filename, _ = _INDEX_FILES[level]
        return os.path.join(self.cache_dir, filename)

    def _load_index(self, level: str) -> list:
        filename, object_key = _INDEX_FILES[level]
        path = self._index_path(level)
        if not os.path.exists(path) or (time.time() - os.path.getmtime(path)) > _INDEX_CACHE_MAX_AGE_SECONDS:
            response = requests.get(f"{OSMIT_ESTRATTI_BASE}/topojson/{filename}", timeout=60)
            response.raise_for_status()
            with open(path, "w") as file_handle:
                file_handle.write(response.text)
        with open(path, "r") as file_handle:
            data = json.load(file_handle)
        return data["objects"][object_key]["geometries"]

    def resolve(self, area: str, level: Optional[AreaLevel] = None, istat: Optional[str] = None) -> AreaSpec:
        levels = [level] if level else ["comune", "provincia", "regione"]
        matches = []
        for candidate_level in levels:
            for feature in self._load_index(candidate_level):
                props = feature.get("properties", {})
                name = props.get("name")
                if name is None:
                    continue
                if istat is not None:
                    if props.get("istat") == istat:
                        matches.append((candidate_level, props))
                    continue
                if area.strip().lower() in name.lower():
                    matches.append((candidate_level, props))

        if not matches:
            raise AreaNotFoundError(f"No area found for '{area}' (level={level or 'any'}, istat={istat})")

        exact = [m for m in matches if m[1]["name"].lower() == area.strip().lower()]
        if len(exact) == 1:
            matches = exact
        elif len(matches) > 1:
            raise AmbiguousAreaError(area, matches)

        candidate_level, props = matches[0]
        return AreaSpec(
            name=props["name"],
            slug=slugify(props["name"]),
            source="osmit",
            level=candidate_level,
            istat_code=props.get("istat"),
            pbf_url=f"{OSMIT_ESTRATTI_BASE}/{props['.osm.pbf']}",
            gpkg_url=f"{OSMIT_ESTRATTI_BASE}/{props['.gpkg']}",
        )
