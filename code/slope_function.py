import geopandas as gpd
import rpy2.robjects as ro
from rpy2.robjects.packages import importr
from rpy2.robjects.conversion import localconverter
import os

# Import R packages in python
geojsonsf = importr('geojsonsf')
dplyr = importr('dplyr')
sf = importr('sf')
stplanr = importr('stplanr')

# DEM interested:
dem_path = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/area.tif' #Pordenonese
# dem_path = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/w51065_s10.tif' # Trento
# dem_path = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/w49565_s10.tif' #Bologna
class SlopeCalculator:

    @staticmethod
    def calc_slope(edges):

        # Convert geopandas dataframe to geojson
        edges_json = edges.to_json()

        # Use the geojsonsf package to convert the geojson to an sf object
        edges_sf = geojsonsf.geojson_sf(edges_json)

        # Assign edges_sf and dem_path to the R environment
        ro.globalenv['edges_sf'] = edges_sf
        ro.globalenv['dem_path'] = dem_path

        # Use the robjects.r method to execute R code
        r_script = """
        library(dplyr)
        library(sf)
        library(stplanr)
        library(raster)
        library(slopes)
        library(geodist)
        library(geojsonsf)
        library(lwgeom)

        edges_sf$group = rnet_group(edges_sf)
        iow_network_clean = edges_sf 
        # %>% filter(group == 1) 
        # iow_network_segments = rnet_breakup_vertices(iow_network_clean)

        # Import and plot DEM
        dem = raster::raster(dem_path)
        res(dem)

        # Get the CRS of the streets and the DEM
        street_crs <- st_crs(iow_network_clean)
        dem_crs <- st_crs(dem)

        # Convert to EPSG:32632
        # iow_network_clean = st_transform(iow_network_clean, crs = 32632)

        # Check if they are different
        if (street_crs != dem_crs) {
        # Convert to EPSG:32632
        iow_network_clean = st_transform(iow_network_clean, crs = 32632)

        # Define the transformer
        st_crs_4326 <- st_crs(4326)

        # Transform road network bounding box to match the CRS of the DEM
        edges_bounds <- st_bbox(iow_network_clean)
        edges_bounds_transformed <- st_transform(st_as_sfc(edges_bounds, crs = st_crs_4326), crs = dem_crs)
        }

        network = iow_network_clean

        #slope calculus
        network$slope = slope_raster(network, dem)
        network$slope = network$slope*100 

        # Compute the summary
        summary_stats = summary(network$slope)
        # Print each individual statistic
        cat("Minimum: ", summary_stats[1], "\n")
        cat("1st Quartile: ", summary_stats[2], "\n")
        cat("Median: ", summary_stats[3], "\n")
        cat("Mean: ", summary_stats[4], "\n")
        cat("3rd Quartile: ", summary_stats[5], "\n")
        cat("Maximum: ", summary_stats[6], "\n")

        network$slope_class = network$slope %>%
        cut(
            breaks = c(0, 3, 5, 8, 10, 20, Inf),
            labels = c("0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", 
                    "10-20: extreme", ">20: impossible"),
            right = F
        )
        round(prop.table(table(network$slope_class))*100,1)

        print(round(prop.table(table(network$slope_class))*100,1))

        # Save the sf object to geojson
        geojson_file <- tempfile(fileext = ".geojson")
        sf::st_write(network, geojson_file)
        geojson_file
        """

        # Execute the R code to get the path of the geojson file
        geojson_file_path = ro.r(r_script)[0]

        # Read the GeoJSON file as a GeoDataFrame
        edges = gpd.read_file(geojson_file_path)
        # Delete the temporary file
        os.remove(geojson_file_path)

        # Delete the DEM file to save memory
        # os.remove(dem_path)

        return edges
