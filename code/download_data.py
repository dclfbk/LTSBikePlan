### Level of Traffic Stress maps with Open Street Map
# This notebook calculates Level of Traffic Stress from Open Street Map data. 

### Setup
import pickle
import osmnx as ox
from mpl_toolkits.axes_grid1 import make_axes_locatable

### Download OSM data

import osmnx as ox
import pandas as pd

# Define the city
city = "Montereale Valcellina, Italy"

# Download the OSM data for Montereale Valcellina, Italy
G = ox.graph_from_place(city)

# Convert the graph into GeoDataFrames
gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)

# plot downloaded graph - this is slow for a large area
#fig, ax = ox.plot_graph(G, node_size=0, edge_color="w", edge_linewidth=0.2)

#print(gdf_edges.columns)
# Index(['osmid', 'name', 'highway', 'oneway', 'reversed', 'length', 'ref',
#        'geometry', 'lanes', 'bridge', 'maxspeed', 'junction', 'access',
#        'est_width', 'tunnel', 'service'],
#       dtype='object')

pickle_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/gdf_data.pkl"

# Save the GeoDataFrames to a pickle file
with open(pickle_path, 'wb') as f:
    pickle.dump((gdf_nodes, gdf_edges, city), f)