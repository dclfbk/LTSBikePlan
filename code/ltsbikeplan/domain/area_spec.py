from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

AreaLevel = Literal["comune", "provincia", "regione"]
AreaSource = Literal["osmit", "osmnx"]

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.\-]+")


def slugify(name: str) -> str:
    """Turn a display name into a filesystem-safe identifier.

    Unlike `utils.sanitize_city_name`, this does NOT split on "-": several
    Italian region names are legitimately hyphenated (e.g. "Trentino-Alto
    Adige", "Emilia-Romagna", "Friuli-Venezia Giulia") and truncating at the
    first hyphen would silently merge distinct areas.
    """
    normalized = unicodedata.normalize("NFKD", name.strip())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.replace(" ", "_")
    return _UNSAFE_CHARS.sub("", ascii_name)


@dataclass(frozen=True)
class AreaSpec:
    name: str
    slug: str
    source: AreaSource
    level: Optional[AreaLevel] = None
    istat_code: Optional[str] = None
    pbf_url: Optional[str] = None
    gpkg_url: Optional[str] = None
    place_query: Optional[str] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # (west, south, east, north), EPSG:4326
    # Path to a local GeoJSON with the area's own boundary polygon - the
    # escape hatch for a comune Nominatim can't geocode to a (Multi)Polygon
    # at all (confirmed 2026-09-04: Pietramelara/061058 has no
    # administrative boundary relation in OSM, just a place=village node -
    # both osmit-estratti and live OSMnx/Overpass place-name resolution
    # fail identically for it, since both ultimately need a boundary
    # relation that doesn't exist). Takes priority over place_query/source
    # in fetch.py's _load_network when set.
    boundary_geojson: Optional[str] = None

    def with_bbox(self, bbox: Tuple[float, float, float, float]) -> "AreaSpec":
        from dataclasses import replace

        return replace(self, bbox=bbox)

    @classmethod
    def from_boundary_geojson(cls, name: str, geojson_path: str, istat_code: Optional[str] = None) -> "AreaSpec":
        from ltsbikeplan.utils import sanitize_city_name

        return cls(
            name=name,
            slug=sanitize_city_name(name),
            source="osmnx",
            level="comune",
            istat_code=istat_code,
            boundary_geojson=geojson_path,
        )

    @classmethod
    def from_city(cls, city: str) -> "AreaSpec":
        from ltsbikeplan.utils import sanitize_city_name

        return cls(name=city, slug=sanitize_city_name(city), source="osmnx", place_query=city)
