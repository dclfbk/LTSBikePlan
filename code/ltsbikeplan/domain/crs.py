from __future__ import annotations

import geopandas as gpd
import pandas as pd

# Single internal CRS used for every metric operation (buffers, distances, slope
# sampling) once edges leave the DEM-driven slope step. LAEA Europe: equal-area,
# covers all of Italy without the UTM-zone split (32N/33N) that silently broke
# multi-region runs before this was introduced.
WORKING_CRS = "EPSG:3035"

# CRS used for on-disk interchange formats (GeoJSON/GeoParquet export, web map).
STORAGE_CRS = "EPSG:4326"

# Row count per chunk for chunked_to_crs. Empirically bisected against a live
# Trento run (comune, ~288k edges after graph_services.py's highway
# whitelist was widened to include footway/path/service): reprojecting half
# the rows (143828, 287656 coordinate pairs) succeeded, the full set
# (287656 rows, 575312 coordinate pairs) raised
# `ValueError: The coordinate array has an invalid shape` from
# geopandas.array.transform - a pyproj 3.7.2/numpy 2.0.2/Python 3.14.4
# threshold bug in the underlying vectorized transform, not a data problem
# (geometries were all valid simple 2-point LineStrings, no NaN/Inf). Set
# well under the point that failed to leave headroom for areas with more
# vertices per geometry (curvier roads) than Trento's.
_TO_CRS_CHUNK_ROWS = 50_000


def chunked_to_crs(gdf: gpd.GeoDataFrame, crs) -> gpd.GeoDataFrame:
    """Same result as `gdf.to_crs(crs)`, but reprojects in row-count-bounded
    chunks - works around the pyproj/numpy/Python 3.14 threshold bug
    described above, which only appears once a single `to_crs()` call's
    total coordinate count gets large enough (a full-comune or bigger edge
    set, now routine since graph_services.py stopped dropping footway/path/
    service edges). A no-op wrapper below `_TO_CRS_CHUNK_ROWS` rows.
    """
    if len(gdf) <= _TO_CRS_CHUNK_ROWS:
        return gdf.to_crs(crs)

    chunks = [gdf.iloc[start : start + _TO_CRS_CHUNK_ROWS].to_crs(crs) for start in range(0, len(gdf), _TO_CRS_CHUNK_ROWS)]
    return gpd.GeoDataFrame(pd.concat(chunks), crs=chunks[0].crs)
