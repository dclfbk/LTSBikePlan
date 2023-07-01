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

I have started working on a Python version (work in progress)
```Python
import os
import urllib.request
import geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.plot import show
import numpy as np
from scipy import ndimage
import pandas as pd
from rasterstats import zonal_stats
from shapely.geometry import LineString

# Download and load the DEM
url = "https://github.com/U-Shift/Declives-RedeViaria/releases/download/0.2/IsleOfWightNASA_clip.tif"
filename = os.path.basename(url)
urllib.request.urlretrieve(url, filename)

# Load the DEM with rasterio
dem = rasterio.open(filename)

# Assume network is a GeoDataFrame
network = gpd.read_file("path_to_network_file")

# Plot the dem and the network
show(dem)
network.plot()

# To get the slope, first we need to calculate the gradient (change in elevation)
dem_array = dem.read(1)
gradient_x, gradient_y = np.gradient(dem_array)

# Calculate slope (converting to degrees)
slope = np.arctan(np.sqrt(gradient_x**2 + gradient_y**2)) * 180 / np.pi
slope = slope * 100 # convert to percentage

# Write out slope as new geotiff
meta = dem.meta
meta.update(dtype=rasterio.float32)

with rasterio.open('slope.tif', 'w', **meta) as dest:
    dest.write(slope.astype(rasterio.float32), 1)

# For each road segment, calculate zonal statistics (mean slope along the line)
slope_stats = zonal_stats(network, 'slope.tif', stats="mean")

# Add slope stats to network dataframe
network['slope'] = [x['mean'] for x in slope_stats]

# Classify slopes
network['slope_class'] = pd.cut(
    network['slope'],
    bins=[0, 3, 5, 8, 10, 20, np.inf],
    labels=["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"],
    include_lowest=True
)

# Calculate proportion of each slope class
slope_class_distribution = round(network['slope_class'].value_counts(normalize=True) * 100, 1)

print(slope_class_distribution)

```
The `rasterstats` package in Python provides a set of raster analysis tools, including functions for computing statistics of raster datasets (e.g., geospatial imagery) based on vector geometries (e.g., polygons, lines, or points).

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

