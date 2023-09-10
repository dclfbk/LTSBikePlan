# This file download data from Open Street Map. 

### Setup
import pickle
import osmnx as ox
from mpl_toolkits.axes_grid1 import make_axes_locatable
import osmnx as ox
from slope_function import SlopeCalculator
import sys

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