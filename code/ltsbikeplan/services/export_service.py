from __future__ import annotations

import os

from ltsbikeplan.domain.crs import STORAGE_CRS, chunked_to_crs


class ExportService:
    """Writes the final LTS edge GeoDataFrame in CRS-aware formats.

    Replaces the original plain-CSV-with-WKT-geometry export, which stored no
    CRS metadata at all and was the root cause of the EPSG:32632 hardcodes
    this refactor removes from maps.py/destination_access.py.
    """

    @staticmethod
    def write_geoparquet(gdf, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        gdf.to_parquet(path)
        return path

    @staticmethod
    def write_geojson(gdf, path: str, crs: str = STORAGE_CRS) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        chunked_to_crs(gdf, crs).to_file(path, driver="GeoJSON")
        return path
