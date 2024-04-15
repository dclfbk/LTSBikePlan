# This file download data from Open Street Map. 

### Setup
import pickle
import osmnx as ox
from mpl_toolkits.axes_grid1 import make_axes_locatable
import osmnx as ox
from slope_function import SlopeCalculator
from slope_function2 import SlopeCalculator2
from slope_function3 import SlopeCalculator3
import sys
import os
import numpy as np
import geopandas as gpd
from sklearn.neighbors import NearestNeighbors
from shapely.geometry import Point
from geopandas.tools import sjoin
import folium

# Function Definitions

# Use features_from_place instead of geometries_from_place
def fetch_building_data(city):
    print(f"Fetching building data for {city}...")
    buildings = ox.features_from_place(city, tags={'building': True})
    print(f"Number of buildings fetched: {len(buildings)}")
    return buildings

# Ensure correct CRS for distance calculations
def calculate_building_distances(gdf_buildings):
    print(f"Calculating distances for {len(gdf_buildings)} buildings...")
    gdf_projected = gdf_buildings.to_crs(epsg=32632)
    building_coords = np.array(list(gdf_projected.geometry.centroid.apply(lambda x: (x.x, x.y))))
    
    nbrs = NearestNeighbors(n_neighbors=2, algorithm='ball_tree').fit(building_coords)
    distances, _ = nbrs.kneighbors(building_coords)
    print(f"Distances calculated: {distances[:, 1]}")
    return distances[:, 1]


def divide_into_quintiles(distances):
    quintiles = np.percentile(distances, [20, 40, 60, 80, 100])
    return quintiles

# def classify_edges_by_quintiles(gdf_edges, gdf_buildings, quintiles):
#     urban_threshold = quintiles[2]  # Third quintile
#     gdf_edges['context'] = 'countryside'  # Default to countryside

#     # Ensure gdf_buildings is in the same CRS as gdf_edges
#     gdf_buildings = gdf_buildings.to_crs(gdf_edges.crs)

#     for index, edge in gdf_edges.iterrows():
#         # Buffer the centroid of the edge
#         edge_centroid = edge.geometry.centroid
#         buffer = edge_centroid.buffer(urban_threshold)

#         # Create a temporary GeoDataFrame for the buffer and set the CRS
#         buffer_gdf = gpd.GeoDataFrame(geometry=[buffer], crs=gdf_edges.crs)

#         # Spatial join to find buildings within the buffer
#         possible_matches = gpd.sjoin(gdf_buildings, buffer_gdf, how='inner', predicate='intersects')
        
#         # Check if there is at least one building within the buffer
#         if not possible_matches.empty:
#             gdf_edges.at[index, 'context'] = 'urban'

#     return gdf_edges

def classify_edges_by_quintiles(gdf_edges, gdf_buildings, quintiles):
    urban_threshold = quintiles[2]  # Third quintile
    print(f"Urban threshold set at {urban_threshold} units")
    gdf_edges['context'] = 'countryside'  # Default to countryside

    gdf_buildings = gdf_buildings.to_crs(gdf_edges.crs)

    for index, edge in gdf_edges.iterrows():
        edge_centroid = edge.geometry.centroid
        buffer = edge_centroid.buffer(urban_threshold)
        buffer_gdf = gpd.GeoDataFrame(geometry=[buffer], crs=gdf_edges.crs)
        possible_matches = gpd.sjoin(gdf_buildings, buffer_gdf, how='inner', predicate='intersects')
        
        if not possible_matches.empty:
            gdf_edges.at[index, 'context'] = 'urban'
            print(f"Edge {index} classified as urban")

    return gdf_edges


# Get the city from command-line arguments
city = sys.argv[1]

def extract_city(citta):
    # Splitting by comma and taking the first part
    first_part = citta.split(",")[0]

    # Handling cases where the city name might have a hyphen (like 'Bolzano - Bozen')
    city_name = first_part.split("-")[0].strip()

    # Replacing spaces with underscores after handling the hyphen
    city_sanitized = city_name.replace(" ", "_")

    return city_sanitized

# Sanitize the city name
city_sanitized = extract_city(city)
print(city_sanitized)
city_images = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/"
# Create the path for the new folder
city_folder_path = os.path.join(city_images, city_sanitized) 

if not os.path.exists(city_folder_path):
    os.makedirs(city_folder_path)

# Download the OSM data for the city/region involved.
G = ox.graph_from_place(city, network_type="all")

# Convert the graph into GeoDataFrames
gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)

# # Filter the major roads
major_roads = ['primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary',
               'tertiary_link', 'residential', 'cycleway',
               'living_street', 'unclassified', 'motorway', 'motorway_link',
               'pedestrian', 'steps', 'track']
gdf_edges = gdf_edges[gdf_edges['highway'].isin(major_roads)]

# Fetch building data and process
gdf_buildings = fetch_building_data(city)
distances = calculate_building_distances(gdf_buildings)
quintiles = divide_into_quintiles(distances)

# Ensure gdf_edges is in the same projected CRS for accurate distance calculations
gdf_edges_projected = gdf_edges.to_crs(epsg=32632)
gdf_edges_classified = classify_edges_by_quintiles(gdf_edges_projected, gdf_buildings, quintiles)

# Convert back to original CRS if needed
gdf_edges = gdf_edges_classified.to_crs(gdf_edges.crs)

# Store the original MultiIndex
original_index = gdf_edges.index

dem_path = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/w51075_s10.tif'

# Transform the gdf_edges using the SlopeCalculator
#gdf_edges = SlopeCalculator.calc_slope(gdf_edges)
#gdf_edges = SlopeCalculator2.calc_slope(gdf_edges,dem_path)
gdf_edges = SlopeCalculator3.calc_slope(gdf_edges,dem_path)

# Reassign the original MultiIndex to gdf_edges2
gdf_edges.index = original_index

# plot downloaded graph - this is slow for a large area
#fig, ax = ox.plot_graph(G, node_size=0, edge_color="w", edge_linewidth=0.2)
#print(gdf_edges.columns)

pickle_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/gdf_data.pkl"

# Save the GeoDataFrames to a pickle file
with open(pickle_path, 'wb') as f:
    pickle.dump((gdf_nodes, gdf_edges, city), f)

# Reproject to WGS84
gdf_edges = gdf_edges.to_crs(epsg=4326)

# Create a colormap for slope classes
color_palette = ["#267300", "#70A800", "#FFAA00", "#E60000", "#A80000", "#730000"]
slope_classes = ["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"]
colors = dict(zip(slope_classes, color_palette))

# Calculate the mean of latitudes and longitudes
mean_latitude = gdf_edges.geometry.apply(lambda geom: geom.centroid.y).mean()
mean_longitude = gdf_edges.geometry.apply(lambda geom: geom.centroid.x).mean()

# Create a folium map centered on the mean of latitudes and longitudes
map_osm = folium.Map(location=[mean_latitude, mean_longitude], zoom_start=11)

# Add slope information to the map
for _, row in gdf_edges.iterrows():
    color = colors.get(str(row['slope_class']), "#000000")  # default color is black
    folium.GeoJson(
        row['geometry'], 
        style_function=lambda _, color=color: {'color': color}  # use default argument to capture color
    ).add_to(map_osm)

# Create a custom legend HTML string
legend_html = '''
<div style="position: fixed; top: 10px; right: 10px; z-index: 1000; background-color: white; padding: 5px; border: 1px solid grey; font-size: 12px;">
<p><b>Slope</b></p>
'''
for slope_class, color in colors.items():
    legend_html += f'<p><i class="fa fa-square" style="color:{color};"></i> {slope_class}</p>'
legend_html += '</div>'

# Add the legend HTML to the map
map_osm.get_root().html.add_child(folium.Element(legend_html))

file_path = os.path.join(city_folder_path, 'slope_map.html')

map_osm.save(file_path)
