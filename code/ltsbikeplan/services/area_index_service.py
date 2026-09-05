from __future__ import annotations

import json
import os
import tempfile
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
        self._dup_name_cache: dict = {}

    def _index_path(self, level: str) -> str:
        filename, _ = _INDEX_FILES[level]
        return os.path.join(self.cache_dir, filename)

    def ensure_cached(self, level: str) -> str:
        """Downloads/refreshes `level`'s topojson if missing or stale and
        returns its local cache path, without parsing it - for callers like
        compute_comuni_superficie_km2 below that need to read the raw file
        directly (e.g. via geopandas' topojson driver) rather than the
        already-decoded properties `_load_index` returns. `_load_index`
        itself is built on top of this, so there's one download rule, not two.
        """
        filename, _ = _INDEX_FILES[level]
        path = self._index_path(level)
        if not os.path.exists(path) or (time.time() - os.path.getmtime(path)) > _INDEX_CACHE_MAX_AGE_SECONDS:
            response = requests.get(f"{OSMIT_ESTRATTI_BASE}/topojson/{filename}", timeout=60)
            response.raise_for_status()
            # Shared across every comune/provincia process - with the
            # comuni cron script now able to run several areas concurrently,
            # multiple processes can race to refresh the same stale index
            # at once. Write-then-rename so a concurrent reader never sees
            # a truncated file mid-download.
            fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, prefix=".tmp_", suffix=".json")
            try:
                with os.fdopen(fd, "w") as file_handle:
                    file_handle.write(response.text)
                os.replace(tmp_path, path)
            except BaseException:
                os.remove(tmp_path)
                raise
        return path

    def _load_index(self, level: str) -> list:
        _, object_key = _INDEX_FILES[level]
        path = self.ensure_cached(level)
        with open(path, "r") as file_handle:
            data = json.load(file_handle)
        return data["objects"][object_key]["geometries"]

    def _duplicate_name_slugs(self, level: str) -> set:
        """Slugs that more than one area at `level` would produce - real for
        comuni (~7900 units, unlike province's ~107): e.g. two distinct
        comuni are both named "Paterno". Left unresolved, both would write
        to the same data/<slug>/ directory and overwrite each other."""
        if level not in self._dup_name_cache:
            from collections import Counter

            counts = Counter(
                slugify(feature["properties"]["name"])
                for feature in self._load_index(level)
                if feature.get("properties", {}).get("name")
            )
            self._dup_name_cache[level] = {slug for slug, count in counts.items() if count > 1}
        return self._dup_name_cache[level]

    def _slug_for(self, level: str, props: dict) -> str:
        slug = slugify(props["name"])
        if slug in self._duplicate_name_slugs(level):
            slug = f"{slug}_{props.get('istat')}"
        return slug

    def list_areas(self, level: AreaLevel) -> list:
        """Every named area at `level` as {name, slug, istat} dicts, slug
        already disambiguated the same way resolve() does - so callers (e.g.
        scripts/list_comuni.py) get the exact slug fetch/compute-lts will
        produce for that area, without duplicating the dedup logic."""
        result = []
        for feature in self._load_index(level):
            props = feature.get("properties", {})
            name = props.get("name")
            if not name:
                continue
            result.append({"name": name, "slug": self._slug_for(level, props), "istat": props.get("istat")})
        return result

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
            slug=self._slug_for(candidate_level, props),
            source="osmit",
            level=candidate_level,
            istat_code=props.get("istat"),
            pbf_url=f"{OSMIT_ESTRATTI_BASE}/{props['.osm.pbf']}",
            gpkg_url=f"{OSMIT_ESTRATTI_BASE}/{props['.gpkg']}",
        )


def compute_comuni_superficie_km2(cache_dir: str) -> dict:
    """Surface area per comune (km²), keyed by ISTAT code - computed from
    the comuni boundary polygons AreaResolver already downloads and caches,
    rather than a second external dataset. ISTAT doesn't publish superficie
    as a simple stable direct-download file (it lives behind the SITUAS
    portal, an interactive web app) - the topojson AreaResolver already
    fetches for name/ISTAT-code resolution turns out to have real polygon
    geometry too (GDAL's topojson driver decodes it directly via
    `geopandas.read_file`), which is enough to derive this ourselves.

    Reprojects to WORKING_CRS (EPSG:3035, equal-area LAEA Europe) before
    computing area - verified against Trento's real-world ~157.9 km²: this
    gives ~159.7 km² (~1% off, OSM boundary precision vs. cadastral -
    acceptable for a comparison-page indicator, not survey-grade).

    18 comuni (small islands - Capri, Procida, Ponza, Ventotene, Isole
    Tremiti - plus a handful of others: Campione d'Italia, Claviere,
    Vajont, Brunate, Blello, Solza, Miagliano, Sueglio, Pero, Calceranica
    al Lago, Cavizzana, Samone, San Paolo Bel Sito) have a properties
    entry in this same topojson (AreaResolver.resolve() can find them by
    name/istat just fine, which is how they were already extracted and
    processed - see NOT the same problem) but GDAL's topojson driver
    decodes no usable geometry for them here, for reasons never tracked
    down (degenerate/dropped arcs at this topojson's simplification
    level, unrelated to OSM extraction). comuni_superficie_patch.json
    fills in exactly those 18 codes, computed once (2026-09) from ISTAT's
    own confini amministrativi geojson (PRO_COM_T field = istat code),
    same EPSG:3035-area method as above - see build_comuni_clusters.py's
    git history for the one-off extraction command if this ever needs
    redoing for a newly-discovered gap (ogr2ogr with a `-where "PRO_COM_T
    IN (...)"` filter against the full national confini file is enough,
    no need to load the ~300MB file into Python).
    """
    import geopandas as gpd

    from ltsbikeplan.assets import asset_path
    from ltsbikeplan.domain.crs import WORKING_CRS

    resolver = AreaResolver(cache_dir)
    path = resolver.ensure_cached("comune")
    gdf = gpd.read_file(path).set_crs("EPSG:4326").to_crs(WORKING_CRS)
    superficie = {row["istat"]: round(row.geometry.area / 1_000_000, 3) for _, row in gdf.iterrows()}

    with open(asset_path("comuni_superficie_patch.json")) as file_handle:
        patch = json.load(file_handle)
    for istat_code, superficie_km2 in patch.items():
        superficie.setdefault(istat_code, superficie_km2)

    return superficie
