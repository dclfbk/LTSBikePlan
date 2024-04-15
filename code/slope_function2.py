import geopandas as gpd
import rasterio
import tempfile
import numpy as np
from osgeo import gdal
from shapely.geometry import mapping
from rasterio.mask import mask
import pandas as pd


class SlopeCalculator2:

    @staticmethod
    def calculate_slope(dem_path):
        # Create a temporary file to store the slope
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as temp_file:
            slope_path = temp_file.name

        # Calculate the slope using GDAL
        gdal.DEMProcessing(slope_path, dem_path, 'slope')

        return slope_path

    @staticmethod
    def extract_slope_for_roads(edges, slope_path):
        # Load the slope raster
        with rasterio.open(slope_path) as slope_raster:
            # Transform edges to the same CRS as the slope raster
            edges = edges.to_crs(slope_raster.crs)

            for _, row in edges.iterrows():
                geom = mapping(row.geometry)
                try:
                    # Mask the slope raster with the geometry
                    out_image, out_transform = mask(slope_raster, [geom], crop=True, nodata=np.nan)
                    out_image = out_image[0]  # Get the first and only band

                    # Compute the mean slope for this segment, ignoring NaN values
                    mean_slope = np.nanmean(out_image)
                    edges.loc[row.name, 'slope'] = mean_slope
                except ValueError:
                    # Skip geometries that do not overlap with the raster
                    edges.loc[row.name, 'slope'] = np.nan

        return edges

    @staticmethod
    def calc_slope(edges, dem_path):
        # Calculate slope from DEM
        slope_path = SlopeCalculator2.calculate_slope(dem_path)

        # Extract slope for road segments
        edges_with_slope = SlopeCalculator2.extract_slope_for_roads(edges, slope_path)

        # Classify slope and calculate summary statistics
        edges_with_slope['slope_class'] = pd.cut(edges_with_slope['slope'], bins=[0, 3, 5, 8, 10, 20, np.inf], 
                                      labels=["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", 
                                              "10-20: extreme", ">20: impossible"], right=False)
        summary_stats = edges_with_slope['slope'].describe()

        # Print each individual statistic
        print(f"Minimum: {summary_stats['min']}\n")
        print(f"1st Quartile: {summary_stats['25%']}\n")
        print(f"Median: {summary_stats['50%']}\n")
        print(f"Mean: {summary_stats['mean']}\n")
        print(f"3rd Quartile: {summary_stats['75%']}\n")
        print(f"Maximum: {summary_stats['max']}\n")

        # Print slope class proportions
        slope_class_proportions = (edges_with_slope['slope_class'].value_counts(normalize=True) * 100).round(1)
        print(slope_class_proportions)

        return edges_with_slope
