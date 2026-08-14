from __future__ import annotations

# Single internal CRS used for every metric operation (buffers, distances, slope
# sampling) once edges leave the DEM-driven slope step. LAEA Europe: equal-area,
# covers all of Italy without the UTM-zone split (32N/33N) that silently broke
# multi-region runs before this was introduced.
WORKING_CRS = "EPSG:3035"

# CRS used for on-disk interchange formats (GeoJSON/GeoParquet export, web map).
STORAGE_CRS = "EPSG:4326"
