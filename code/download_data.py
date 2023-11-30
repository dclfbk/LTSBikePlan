# This file download data from Open Street Map. 

### Setup
import pickle
import osmnx as ox
from mpl_toolkits.axes_grid1 import make_axes_locatable
import osmnx as ox
from slope_function import SlopeCalculator
import sys
import numpy as np
import geopandas as gpd
from sklearn.neighbors import NearestNeighbors
from shapely.geometry import Point
from geopandas.tools import sjoin

# Function Definitions

# Use features_from_place instead of geometries_from_place
def fetch_building_data(city):
    buildings = ox.features_from_place(city, tags={'building': True})
    return buildings

# Ensure correct CRS for distance calculations
def calculate_building_distances(gdf_buildings):
    # Convert to a projected CRS
    gdf_projected = gdf_buildings.to_crs(epsg=32632)
    building_coords = np.array(list(gdf_projected.geometry.centroid.apply(lambda x: (x.x, x.y))))
    
    nbrs = NearestNeighbors(n_neighbors=2, algorithm='ball_tree').fit(building_coords)
    distances, _ = nbrs.kneighbors(building_coords)
    return distances[:, 1]

def divide_into_quintiles(distances):
    quintiles = np.percentile(distances, [20, 40, 60, 80, 100])
    return quintiles

def classify_edges_by_quintiles(gdf_edges, gdf_buildings, quintiles):
    urban_threshold = quintiles[2]  # Third quintile
    gdf_edges['context'] = 'countryside'  # Default to countryside

    # Ensure gdf_buildings is in the same CRS as gdf_edges
    gdf_buildings = gdf_buildings.to_crs(gdf_edges.crs)

    for index, edge in gdf_edges.iterrows():
        # Buffer the centroid of the edge
        edge_centroid = edge.geometry.centroid
        buffer = edge_centroid.buffer(urban_threshold)

        # Create a temporary GeoDataFrame for the buffer and set the CRS
        buffer_gdf = gpd.GeoDataFrame(geometry=[buffer], crs=gdf_edges.crs)

        # Spatial join to find buildings within the buffer
        possible_matches = gpd.sjoin(gdf_buildings, buffer_gdf, how='inner', predicate='intersects')
        
        # Check if there is at least one building within the buffer
        if not possible_matches.empty:
            gdf_edges.at[index, 'context'] = 'urban'

    return gdf_edges

# Get the city from command-line arguments
city = sys.argv[1]

# Download the OSM data for the city/region involved.
G = ox.graph_from_place(city, network_type="all")

# Convert the graph into GeoDataFrames
gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)

# # Filter the major roads
major_roads = ['primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary',
               'tertiary_link', 'trunk', 'trunk_link', 'residential', 'cycleway',
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

# Transform the gdf_edges using the SlopeCalculator
gdf_edges = SlopeCalculator.calc_slope(gdf_edges)

# Reassign the original MultiIndex to gdf_edges2
gdf_edges.index = original_index

# plot downloaded graph - this is slow for a large area
#fig, ax = ox.plot_graph(G, node_size=0, edge_color="w", edge_linewidth=0.2)
#print(gdf_edges.columns)

pickle_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/gdf_data.pkl"

# Save the GeoDataFrames to a pickle file
with open(pickle_path, 'wb') as f:
    pickle.dump((gdf_nodes, gdf_edges, city), f)