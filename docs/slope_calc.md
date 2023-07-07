<div style="text-align: justify;">
Here's what I have found so far regarding the slope calculus using geospatial data:

[OSM and DEM]
In OpenStreetMap, an open-source, collaborative mapping project, "incline" is a key used to denote the steepness of a road, path, or other route. This data is particularly useful for routing software that caters to people with mobility issues or for those planning a route for cycling or hiking.
The incline value is typically given as a percentage (%). Positive values indicate an uphill incline (e.g., incline=10% means that for every 100 meters you move forward, you would ascend 10 meters). Negative values indicate a downhill incline (e.g., incline=-10%). Sometimes, instead of a percentage, the incline might be tagged as "up" or "down" if the exact steepness is unknown. For stairways, the incline can be defined as "steep" or "shallow".
hanging inclines or bridges: The incline key can also be used to represent situations where the incline changes, like on a footbridge that goes up and then down.

Usage: The incline key is most often used on ways, specifically sections of ways that have a steep incline. It's most commonly found on steps (tagged with highway=steps) and marked as incline=up or incline=down.

On nodes: The incline key is rarely used on nodes, since nodes don't have direction. If it's necessary to denote an incline at a specific point, it's recommended to tag a segment of the way between two nodes instead.

Estimates: If the exact incline value is unknown, it can be tagged as incline=up or incline=down. Alternatively, a rough estimate can be used with a supplementary fixme=check incline tag to indicate that the incline should be checked for accuracy.

Relationship between gradient and angle: The document also provides formulas to convert between the gradient (expressed in percent) and the angle (expressed in degrees).

Common & extreme inclines: It mentions common incline values found on roads (typically between -25% to 25%) and provides examples of some of the steepest known inclines.

Hops: It also mentions the usage of incline=up/down for ways with many small inclines, although this use is disputed within the OSM community and there's no clear consensus on how it should be handled.

At this link you can see a small procedure to integrate in OpenStreetMap data regarding the slopeness using a DEM that can be adapted using Tinitaly DEM ([https://tinitaly.pi.ingv.it/](https://tinitaly.pi.ingv.it/)). Here's the code in R: [https://ropensci.github.io/slopes/articles/roadnetworkcycling.html](https://ropensci.github.io/slopes/articles/roadnetworkcycling.html)

In summary, it follow three steps:
- Download of road network from OpenStreetMap
- Prepare the network
- Compute slopes and export the map in html.
  
For the slopes, the slope_raster() function, to retrieve the z values from a digital elevation model was used. This raster was obtained from STRM NASA mission (but we can use Tinitaly DEM) or Coperticus (it works for all Europe). [https://land.copernicus.eu/imagery-in-situ/eu-dem](https://land.copernicus.eu/imagery-in-situ/eu-dem)

```R
# Import and plot DEM
u = "https://github.com/U-Shift/Declives-RedeViaria/releases/download/0.2/IsleOfWightNASA_clip.tif"
f = basename(u)
download.file(url = u, destfile = f, mode = "wb")
dem = raster::raster(f)
# res(dem) #27m of resolution
network = iow_network_segments

library(raster)
plot(dem)
plot(sf::st_geometry(network), add = TRUE) #check if they overlay

# Get the slope value for each segment (abs), using slopes package
library(slopes)
library(geodist)
network$slope = slope_raster(network, dem)
network$slope = network$slope*100 #percentage
summary(network$slope) #check the values

# Classify slopes
network$slope_class = network$slope %>%
  cut(
    breaks = c(0, 3, 5, 8, 10, 20, Inf),
    labels = c("0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", 
               "10-20: extreme", ">20: impossible"),
    right = F
  )
round(prop.table(table(network$slope_class))*100,1)
```

I have started working on a Python version:
```Python
#slope calc using SRTM dem

import osmnx as ox
import folium
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from shapely.geometry import LineString
from pyproj import CRS, Transformer
from rasterio.windows import Window
from geopy.distance import geodesic

# Get the network
G = ox.graph_from_place('Montereale Valcellina, Italy', network_type='all')
edges = ox.graph_to_gdfs(G, nodes=False)

# Filter the major roads
major_roads = ['primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary',
               'tertiary_link', 'trunk', 'trunk_link', 'residential', 'cycleway',
               'living_street', 'unclassified', 'motorway', 'motorway_link',
               'pedestrian', 'steps', 'track']
edges = edges[edges['highway'].isin(major_roads)]

# Set the path to the DEM file
dem_path = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/area_interested.tif'

# Load the DEM
dem = rasterio.open(dem_path)

# Define a Transformer from EPSG:4326 to a local projection (in this case, the Friuli Grid, EPSG:3004)
transformer = Transformer.from_crs(CRS('EPSG:4326'), CRS('EPSG:3004'), always_xy=True)

# Calculate the slope
def calc_slope(row):
    coords = row['geometry'].coords.xy
    start = (coords[0][0], coords[1][0])
    end = (coords[0][-1], coords[1][-1])

    start_elevation = float(list(dem.sample([start]))[0][0])
    end_elevation = float(list(dem.sample([end]))[0][0])
    dz = end_elevation - start_elevation

    if abs(dz) > 100:  # Adjust this value based on what you consider to be an "outlier"
        return 0

    start_x, start_y = transformer.transform(*start)
    end_x, end_y = transformer.transform(*end)
    dx = end_x - start_x
    dy = end_y - start_y
    distance = np.sqrt(dx ** 2 + dy ** 2)

    slope = (dz / distance) * 100 if distance != 0 else 0
    return slope

# Apply function to each row in the GeoDataFrame
edges['slope'] = edges.apply(calc_slope, axis=1)

# Replace NaN slope values with 0
edges['slope'] = edges['slope'].fillna(0)

# Classify slopes
edges['slope_class'] = pd.cut(edges['slope'],
                              bins=[-30, 3, 5, 8, 10, 20, np.inf],
                              labels=["0-3: flat", "3-5: mild", "5-8: medium",
                                      "8-10: hard", "10-20: extreme", ">20: impossible"],
                              right=False)
edges['slope_class'] = edges['slope_class'].fillna("0-3: flat")

# Calculate the proportion of each slope class
slope_class_distribution = round(edges['slope_class'].value_counts(normalize=True) * 100, 1)
print(slope_class_distribution)


```
The `rasterstats` [https://pythonhosted.org/rasterstats/](https://pythonhosted.org/rasterstats/) package in Python provides a set of raster analysis tools, including functions for computing statistics of raster datasets (e.g., geospatial imagery) based on vector geometries (e.g., polygons, lines, or points).

In this context, zonal statistics is a spatial analysis operation where statistics are computed for regions (zones) defined by the geometries in a vector layer.

The way zonal statistics work in this scenario is by calculating the mean slope values along each road segment in the network. The mean value of all the raster cells that fall within a road segment is calculated, providing a single summary statistic for that segment.

In more detail, the steps are:

1. For each road segment in the network (each line in the `geopandas` GeoDataFrame), the `rasterstats.zonal_stats` function is applied. This function takes two main inputs: the vector geometries (in this case, the road segments) and a raster dataset (in this case, a raster of slope values).

2. The `zonal_stats` function overlays the vector geometries on the raster dataset, effectively "cutting out" the raster values that fall within each road segment.

3. For each road segment, the function then calculates the statistic specified by the `stats` argument (in this case, "mean"). This involves taking the mean of all the raster cell values within each road segment.

4. The result is a list of dictionaries, where each dictionary corresponds to a road segment and contains the calculated statistics. This list is then added to the `network` GeoDataFrame as a new column, with each mean slope value matched to the corresponding road segment.

The end result is that each road segment in the `network` GeoDataFrame has an associated mean slope value, which is the average of the slope values of all the raster cells that fall within that segment.

Regarding Tinitaly the procedure for downloading data is pretty simple. You download the full version or some squares (Regions) of interest, then with QGIS you merge everything together and save the file somewhere. You can also set null data for the sea etc.

[OSM AND SRTM GL3 dataset (free)]

The author here created an open-source hike planning app and route optimization engine that supplement the functionality of proprietary sites.
The repo here [https://github.com/evandiewald/trail-mapping](https://github.com/evandiewald/trail-mapping).
Interestingly it doesn't use DEM for accessing info on slope and elevation but the NASA free dataset cited above that he uses for creating elevation profiles.

Here's the article [https://towardsdatascience.com/planning-the-perfect-hike-with-networkx-and-openstreetmap-2fbeaded3cc6](https://towardsdatascience.com/planning-the-perfect-hike-with-networkx-and-openstreetmap-2fbeaded3cc6)


Here some interesting videos on how to compute slope calculus using DEMs [https://www.youtube.com/watch?v=2g526ZoMu24&ab_channel=OpenSourceOptions](https://www.youtube.com/watch?v=2g526ZoMu24&ab_channel=OpenSourceOptions)[https://www.youtube.com/watch?v=5dDZeEXws9Q&ab_channel=MakingSenseRemotely](https://www.youtube.com/watch?v=5dDZeEXws9Q&ab_channel=MakingSenseRemotely)
</div>

