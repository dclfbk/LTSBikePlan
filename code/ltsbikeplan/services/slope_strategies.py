from __future__ import annotations

import json
import os
import tempfile

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


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


class SlopeCalculatorGDAL:
    @staticmethod
    def calculate_slope(dem_path):
        from osgeo import gdal

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as temp_file:
            slope_path = temp_file.name
        gdal.DEMProcessing(slope_path, dem_path, "slope")
        return slope_path

    @staticmethod
    def extract_slope_for_roads(edges, slope_path):
        with rasterio.open(slope_path) as slope_raster:
            edges = edges.to_crs(slope_raster.crs)
            slope_values = []
            for _, row in edges.iterrows():
                geom = mapping(row.geometry)
                try:
                    out_image, _ = mask(slope_raster, [geom], crop=True, nodata=np.nan)
                    slope_values.append(np.nanmean(out_image[0]))
                except ValueError:
                    slope_values.append(np.nan)
        edges = edges.copy()
        edges["slope"] = slope_values
        return edges

    @staticmethod
    def calc_slope(edges, dem_path):
        slope_path = SlopeCalculatorGDAL.calculate_slope(dem_path)
        edges_with_slope = SlopeCalculatorGDAL.extract_slope_for_roads(edges, slope_path)
        edges_with_slope["slope_class"] = pd.cut(
            edges_with_slope["slope"],
            bins=[0, 3, 5, 8, 10, 20, np.inf],
            labels=["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"],
            right=False,
        )
        return edges_with_slope


class SlopeCalculatorRasterioSimple:
    """Pure-Python fallback slope strategy without GDAL/richdem/rpy2.

    Uses a lightweight gradient approximation over DEM and samples mean slope
    along each road segment.
    """

    @staticmethod
    def calculate_slope(dem_path):
        with rasterio.open(dem_path) as src:
            dem = src.read(1).astype("float64")
            transform = src.transform
            xres = abs(transform.a) if transform.a else 1.0
            yres = abs(transform.e) if transform.e else 1.0

            gy, gx = np.gradient(dem, yres, xres)
            slope = np.sqrt(gx * gx + gy * gy) * 100.0
            slope = np.clip(slope, 0, 100)

            profile = src.profile
            profile.update(dtype="float32", count=1)

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as temp_file:
            slope_path = temp_file.name

        with rasterio.open(slope_path, "w", **profile) as dst:
            dst.write(slope.astype("float32"), 1)
        return slope_path

    @staticmethod
    def calc_slope(edges, dem_path):
        slope_path = SlopeCalculatorRasterioSimple.calculate_slope(dem_path)
        edges_with_slope = SlopeCalculatorGDAL.extract_slope_for_roads(edges, slope_path)
        edges_with_slope["slope_class"] = pd.cut(
            edges_with_slope["slope"],
            bins=[0, 3, 5, 8, 10, 20, np.inf],
            labels=["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"],
            right=False,
        )
        return edges_with_slope


class SlopeCalculatorRichdem:
    @staticmethod
    def calculate_slope(dem_path):
        import richdem as rd

        dem = rd.LoadGDAL(dem_path)
        slope_radians = rd.TerrainAttribute(dem, attrib="slope_riserun")
        slope_percentage = np.tan(slope_radians) * 100
        slope_percentage[slope_percentage < 0] = 0
        slope_percentage[slope_percentage > 100] = 100
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as temp_file:
            slope_path = temp_file.name
            rd.SaveGDAL(slope_path, slope_percentage)
        return slope_path

    @staticmethod
    def extract_slope_for_roads(edges, slope_path):
        with rasterio.open(slope_path) as slope_raster:
            edges = edges.to_crs(slope_raster.crs)
            slope_values = []
            for _, row in edges.iterrows():
                geom = mapping(row.geometry)
                try:
                    out_image, _ = mask(slope_raster, [geom], crop=True, nodata=np.nan)
                    slope_values.append(np.nanmean(out_image[0]))
                except ValueError:
                    slope_values.append(np.nan)
        edges = edges.copy()
        edges["slope"] = slope_values
        return edges

    @staticmethod
    def calc_slope(edges, dem_path):
        slope_path = SlopeCalculatorRichdem.calculate_slope(dem_path)
        edges_with_slope = SlopeCalculatorRichdem.extract_slope_for_roads(edges, slope_path)
        edges_with_slope["slope_class"] = pd.cut(
            edges_with_slope["slope"],
            bins=[0, 3, 5, 8, 10, 20, np.inf],
            labels=["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"],
            right=False,
        )
        return edges_with_slope
