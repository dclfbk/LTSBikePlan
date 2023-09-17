from flask import Flask, render_template, request, jsonify
import geopandas as gpd
import pandas as pd
import osmnx as ox
import networkx as nx
from shapely.geometry import Point
from shapely import wkt

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index_isomap.html')

@app.route('/calculate')
def calculate():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    # Load data
    all_lts_df = pd.read_csv("/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/Montereale_Valcellina_all_lts.csv")
    all_lts_df['geometry'] = all_lts_df['geometry'].apply(wkt.loads)
    all_lts = gpd.GeoDataFrame(all_lts_df, geometry='geometry')
    all_lts.crs = "EPSG:32632"
    #all_lts_projected = all_lts.to_crs(epsg=4326)
    
    gdf_nodes = pd.read_csv("/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/Montereale_Valcellina_gdf_nodes.csv", index_col=0)
    
    filepath = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/Montereale_Valcellina_lts.graphml"
    G_lts = ox.load_graphml(filepath)
    G_lts = ox.project_graph(G_lts, to_crs="EPSG:4326")
    
    remove_nodes = True
    
    G1 = G_lts.copy()
    G2 = G_lts.copy()
    G3 = G_lts.copy()
    G4 = G_lts.copy()

    # Get the subset of the DataFrame
    edges_to_remove = all_lts[all_lts['lts'] != 1]
    # Create a list of edges based on the u, v, and key columns
    edges_list = list(zip(edges_to_remove['u'], edges_to_remove['v'], edges_to_remove['key']))
    # Remove those edges from the graph
    G1.remove_edges_from(edges_list)

    #To the same for the others
    edges_to_remove_G2 = all_lts[(all_lts['lts'] > 2) & (all_lts['lts'] == 0)]
    edges_list_G2 = list(zip(edges_to_remove_G2['u'], edges_to_remove_G2['v'], edges_to_remove_G2['key']))
    G2.remove_edges_from(edges_list_G2)

    edges_to_remove_G3 = all_lts[(all_lts['lts'] > 3) & (all_lts['lts'] == 0)]
    edges_list_G3 = list(zip(edges_to_remove_G3['u'], edges_to_remove_G3['v'], edges_to_remove_G3['key']))
    G3.remove_edges_from(edges_list_G3)

    edges_to_remove_G4 = all_lts[(all_lts['lts'] == 0)]
    edges_list_G4 = list(zip(edges_to_remove_G4['u'], edges_to_remove_G4['v'], edges_to_remove_G4['key']))
    G4.remove_edges_from(edges_list_G4)

    if remove_nodes == True:
        G1.remove_nodes_from(gdf_nodes[gdf_nodes['lts'] != 1].index)
        G2.remove_nodes_from(gdf_nodes[gdf_nodes['lts'] > 2].index)
        G3.remove_nodes_from(gdf_nodes[gdf_nodes['lts'] > 3].index)

    center_node = ox.distance.nearest_nodes(G1, lon, lat)  # using lat and lon from request args
    G1b = ox.project_graph(G1)
    G2b = ox.project_graph(G2)
    G3b = ox.project_graph(G3)
    G4b = ox.project_graph(G4)

    iso_colors = ox.plot.get_colors(n=4, cmap='plasma', start=0, return_hex=True)
    travel_speed = 15  # biking speed in km/hour
    trip_time = 15  # 15 minutes

    meters_per_minute = travel_speed * 1000 / 60 
    for G in [G1b, G2b, G3b, G4b]:
        for u, v, k, data in G.edges(data=True, keys=True):
            data['time'] = data['length'] / meters_per_minute

    node_colors = {}
    graphs = [G4b, G3b, G2b, G1b]
    for i, G in enumerate(graphs):
        subgraph = nx.ego_graph(G, center_node, radius=trip_time, distance='time')
        for node in subgraph.nodes():
            node_colors[node] = iso_colors[i]

    # Return the necessary data for plotting.
    nodes_data = [{"id": node, "color": node_colors.get(node, '#999999')} for node in G4b.nodes()]
    edges_data = [{"source": u, "target": v, "time": data['time']} for u, v, _, data in G4b.edges(data=True, keys=True)]

    # Return the necessary data for plotting.
    nodes_data = [{
        "id": node,
        "lat": G4b.nodes[node]['y'],  # get lat from the node's attributes
        "lon": G4b.nodes[node]['x'],  # get lon from the node's attributes
        "color": node_colors.get(node, '#999999')
    } for node in G4b.nodes()]

    edges_data = [{
        "source": u,
        "target": v,
        "source_lat": G4b.nodes[u]['y'],  # get source lat from the graph
        "source_lon": G4b.nodes[u]['x'],  # get source lon from the graph
        "target_lat": G4b.nodes[v]['y'],  # get target lat from the graph
        "target_lon": G4b.nodes[v]['x'],  # get target lon from the graph
        "time": data['time']
    } for u, v, _, data in G4b.edges(data=True, keys=True)]

    return jsonify({"nodes": nodes_data, "edges": edges_data})

if __name__ == '__main__':
    app.run(debug=True)
