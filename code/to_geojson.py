import pandas as pd
import geopandas as gpd
from shapely import wkt

# Load the node CSV
nodes_df = pd.read_csv('/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/Pordenone_gdf_nodes.csv')
# Convert the 'geometry' column from WKT to Shapely geometries
nodes_df['geometry'] = nodes_df['geometry'].apply(wkt.loads)
# Create a GeoDataFrame for nodes
nodes_gdf = gpd.GeoDataFrame(nodes_df, geometry='geometry', crs='EPSG:4326')

# Load the edge CSV
edges_df = pd.read_csv('/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/Pordenone_all_lts.csv')
# Convert the 'geometry' column from WKT to Shapely geometries
edges_df['geometry'] = edges_df['geometry'].apply(wkt.loads)
# Create a GeoDataFrame for edges
edges_gdf = gpd.GeoDataFrame(edges_df, geometry='geometry', crs='EPSG:4326')

# Combine nodes and edges into a single GeoDataFrame
combined_gdf = nodes_gdf.append(edges_gdf, ignore_index=True)

# Save the combined GeoDataFrame as a GeoJSON file
output_file_path = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/exported/Pordenone.geojson'
combined_gdf.to_file(output_file_path, driver='GeoJSON')
