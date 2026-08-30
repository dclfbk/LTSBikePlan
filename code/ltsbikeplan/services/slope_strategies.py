from __future__ import annotations

import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from ltsbikeplan.domain.crs import chunked_to_crs

_SLOPE_CLASS_BINS = [0, 3, 5, 8, 10, 20, np.inf]
_SLOPE_CLASS_LABELS = ["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"]


def _grade_percent_along_line(dem: rasterio.DatasetReader, dem_nodata, geometry, length_m: float) -> float:
    """Percent grade for one edge: total |elevation change| between
    consecutive VERTICES of the edge's own geometry - each point-sampled
    directly from the DEM - divided by the edge's real length.

    This replaces an earlier approach (masking a precomputed per-cell
    slope raster with the edge's footprint, then averaging the touched
    cells) that measurably produced physically impossible readings: a
    real check against Trento's "Strada Imperiale" (a gently-graded
    hillside road next to the Doss Trento quarry cliffs) found edges
    reading 55-86% grade there, while the true elevation change between
    those same edges' own endpoints - fetched from the identical
    Mapterhorn tiles - was 3-6%. The mask-and-average approach let a
    single raster cell touching a nearby vertical rock face dominate a
    short edge's mean, even though the road itself never goes near that
    cliff. Point-sampling exactly on the road's own vertices can only
    ever read what's really under the bike.

    `length_m` is the edge's own pre-existing `length` (osmnx's geodesic
    length, computed before any reprojection) rather than
    `geometry.length` on the reprojected geometry - Mapterhorn's DEM CRS
    is Web Mercator (EPSG:3857), whose projected-meter distances overstate
    true ground distance away from the equator by 1/cos(latitude) (~1.4x
    at Trento's ~46N), which would understate every grade computed against
    it.
    """
    if length_m is None or not np.isfinite(length_m) or length_m <= 0:
        return np.nan
    coords = list(geometry.coords)
    if len(coords) < 2:
        return np.nan
    elevations = np.array([value[0] for value in dem.sample(coords)], dtype=float)
    if dem_nodata is not None:
        elevations[elevations == dem_nodata] = np.nan
    if np.any(np.isnan(elevations)):
        return np.nan
    total_rise = np.abs(np.diff(elevations)).sum()
    return 100.0 * total_rise / length_m


def slope_from_dem(edges, dem_path: str):
    """The actual slope computation for every SlopeService strategy except
    "v1" (SlopeCalculatorR, a separate R-based implementation, untouched).
    Point-sampling the DEM directly (see _grade_percent_along_line) needs
    nothing beyond rasterio - GDAL's DEMProcessing and richdem's
    TerrainAttribute (the old v2/v3 strategies' actual work) are gone, not
    just skipped, because both were computing the same wrong thing: a
    precomputed per-cell slope raster masked+averaged over each edge's
    footprint. "v2"/"v3" remain selectable strategy names (SlopeService
    still accepts them) purely for backward compatibility with any
    existing caller/config - they all resolve to this one function now.
    """
    with rasterio.open(dem_path) as dem:
        edges_proj = chunked_to_crs(edges, dem.crs)
        dem_nodata = dem.nodatavals[0] if dem.nodatavals else None
        slopes = [
            _grade_percent_along_line(dem, dem_nodata, geometry, length)
            for geometry, length in zip(edges_proj.geometry, edges_proj["length"])
        ]
    edges_with_slope = edges_proj.copy()
    edges_with_slope["slope"] = slopes
    edges_with_slope["slope_class"] = pd.cut(
        edges_with_slope["slope"], bins=_SLOPE_CLASS_BINS, labels=_SLOPE_CLASS_LABELS, right=False
    )
    return edges_with_slope


class SlopeCalculatorR:
    @staticmethod
    def calc_slope(edges, dem_path: str):
        import rpy2.robjects as ro
        from rpy2.robjects.packages import importr

        geojsonsf = importr("geojsonsf")
        importr("dplyr")
        importr("sf")
        importr("stplanr")

        edges_json = edges.to_json()
        edges_sf = geojsonsf.geojson_sf(edges_json)
        ro.globalenv["edges_sf"] = edges_sf
        ro.globalenv["dem_path"] = dem_path

        r_script = """
        library(dplyr); library(sf); library(stplanr); library(raster)
        library(slopes); library(geodist); library(geojsonsf); library(lwgeom)
        edges_sf$group = rnet_group(edges_sf)
        network = edges_sf
        dem = raster::raster(dem_path)
        street_crs <- st_crs(network)
        dem_crs <- st_crs(dem)
        if (street_crs != dem_crs) {
          network = st_transform(network, crs = 32632)
        }
        network$slope = slope_raster(network, dem) * 100
        network$slope_class = network$slope %>% cut(
          breaks = c(0, 3, 5, 8, 10, 20, Inf),
          labels = c("0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"),
          right = F
        )
        geojson_file <- tempfile(fileext = ".geojson")
        sf::st_write(network, geojson_file)
        geojson_file
        """
        geojson_file_path = ro.r(r_script)[0]
        with open(geojson_file_path, "r") as file_handle:
            out_edges_geojson = json.load(file_handle)
        out_edges = gpd.GeoDataFrame.from_features(out_edges_geojson["features"], crs="EPSG:32632")
        os.remove(geojson_file_path)
        return out_edges
