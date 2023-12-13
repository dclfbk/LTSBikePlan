import os
import subprocess

# Example city name - replace this with dynamic city name retrieval logic
#city = os.environ.get('CITY', 'Default City Name')
base_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/"
code_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/code/"
# Sanitize the city name
#city_sanitized = city.split(",")[0].replace(" ", "_")
city_sanitized = "Trento"
#city_path = f"{base_path}{city_sanitized}"
city_path = f"{base_path}{city_sanitized}"

img_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/images"
city_img_path = os.path.join(img_path, city_sanitized)



#Constructing paths for multiple images
lts_image_names = ["slope_map.html", "lts_map.html", "choropleth_lts_map.html"]
esda_image_names = ["network_base.png", "streetnetworkorientation_plot.png", "sno_polar_plot.png"]
network_image_names = ["nodes_degree_centrality.png", 
                       "nodes_closeness_centrality.png",
                       "nodes_betweenness_centrality.png",
                       "edge_betweenness_centrality.png",
                       "lts_distrib_nodes_plot.png",
                       "lts_distrib_edges_plot.png",
                       "nodess_betweenness_centrality.png",
                       "nodess_closeness_centrality.png",
                       "nodess_betweenness_centrality.png",
                       "edgez_betweenness_centrality.png",
                       "deg_central_map.png",
                       "deg_central_map_top_nodes.png",
                       "clos_central_map.png",
                       "clos_central_map_top_nodes.png",
                       "betw_central_map.png",
                       "betw_central_map_top_nodes.png",
                       "edge_bet_central_map.png",
                       "edge_bet_central_map_top_nodes.png",
                       "g_high_stres_map.png",
                       "component_1.png",
                       "component_2.png",
                       "component_3.png",
                       "component_4.png",
                       "component_5.png",
                       "kde_est_simplifiedgraph.png",
                       "nearest_poi_plot.png",
                       ]
clu_image_names = ["dbscan_lts_cluster_geo.png","dbscan_lts_cluster.png","hdbscan_lts_cluster_geo.png","hdbscan_lts_cluster.png","optics_lts_cluster_geo.png","optics_lts_cluster.png"]
acc_image_names = ["accident_map.html", 
               "heatmap_map.html", 
               "kde_map.html",
               "frequencyaccidentsbyroads_plot.png",
               "accidentsbynumberlanes_plot.png",
               "accidentsbymaxspeed_plot.png",
               "lanes_speed_distribution_plot.png",
               "accidents_lts_plot.png", 
               "perc_accidents_lts_plot.png",
               "accidents_stress_level_plot.png",
               "perc_accidents_stress_level_plot.png",
               "accidents_lts_intersection_plot.png",
               "perc_accidents_lts_intersection_plot.png",
               "accidents_stress_level_intersection_plot.png",
               "perc_accidents_stress_level_intersection_plot.png",
               "DBSCAN_accident_clusters_plot.png",
               "choropleth_lts_accidents_map.html"]
gap_image_names = ["Top10connectedcomponents_plot.png",
                   "highlowstresscomponents_plot.png", 
                   "gaps_plot.png",
                   "contact_nodes_plot.png",
                   "heter_gapclosure_benefits.png",
                   "gaps_classified_plot.html"]

da_image_names = ["hexagonal_grid_population.html", "bna_score_map.html"]
sump_image_names = ["gap_quadrants.html", "risk_accidents_hexagon.html"]

lts_image_paths = [os.path.join(city_img_path, img) for img in lts_image_names]
esda_image_paths = [os.path.join(city_img_path, img) for img in esda_image_names]
acc_image_paths = [os.path.join(city_img_path, img) for img in acc_image_names]
clu_image_paths = [os.path.join(city_img_path, img) for img in clu_image_names]
net_image_paths = [os.path.join(city_img_path, img) for img in network_image_names]
gap_image_paths = [os.path.join(city_img_path, img) for img in gap_image_names]
da_image_paths = [os.path.join(city_img_path, img) for img in da_image_names]
sump_image_paths = [os.path.join(city_img_path, img) for img in sump_image_names]


accident_file_exists = os.path.exists(os.path.join(base_path, "accidents_trento.geojson"))

# Markdown Content
markdown_content = f"""

<div class='blue-stripe-header'>
<h2>{city_sanitized} - Level of Traffic Stress Bike Planning and Infrastructure Network Analysis for Safe and Accessible Cycling</h2>

</div>

## Introduction 

<div class='introduction-text'>

This report offers an in-depth analysis of a selected region's road network, focusing on the Level of Traffic Stress (LTS) and its relation to perceived risk. It integrates slope data from OpenStreetMap and uses DBSCAN, HDBSCAN, and OPTICS algorithms for cluster analysis to identify areas of high stress. 
The study includes a classical network analysis, examining various centrality metrics and strongly connected components, using LTS values as weights, and evaluates intersection density for bikeability. 
Additionally, it assesses travel times to points of interest and identifies stress gaps using a modified IPDC procedure. 
The report also features a destination access analysis to calculate region's bike network analysis score, categorizing common destinations within an H3 hexagonal grid, and analyzes accidents in relation to BNA scores and connectivity. 
The goal is to shed light on the network's stress levels, bikeability, and safety.
<div/>

## Section 1: Slope and Level of Traffic Stress

![Slope Map]({lts_image_paths[0]})

![Level of Traffic Stress Map]({lts_image_paths[1]})

![LTS H3 Choropleth map]({lts_image_paths[2]})

## Section 2: Exploratory Spatial Data Analysis

![City Network]({esda_image_paths[0]})

![Street Network Orientation]({esda_image_paths[1]})

![Polar Plot]({esda_image_paths[2]})

## Section 3: Cluster Analysis
![DBSCAN High Stress Map]({clu_image_paths[0]})

![DBSCAN High Stress]({clu_image_paths[1]})

![HDBSCAN High Stress Map]({clu_image_paths[2]})

![HDBSCAN High Stress]({clu_image_paths[3]})

![OPTICS High Stress Map]({clu_image_paths[4]})

![OPTICS High Stress]({clu_image_paths[5]})

## Section 4: Network Analysis

![Nodes Degree Centrality]({net_image_paths[0]})

![Nodes Closeness Centrality]({net_image_paths[1]})

![Nodes Betweenness Centrality]({net_image_paths[2]})

![Edges Betweenness Centrality]({net_image_paths[3]})

![LTS Distribution for Nodes]({net_image_paths[4]})

![LTS Distribution for Edges]({net_image_paths[5]})

![Nodes Degree Centrality weighted by LTS]({net_image_paths[6]})

![Nodes Closeness Centrality weighted by LTS]({net_image_paths[7]})

![Nodes Betweenness Centrality weighted by LTS]({net_image_paths[8]})

![Edges Betweenness Centrality weighted by LTS]({net_image_paths[9]})

![Histogram of Degree Centrality]({net_image_paths[10]})

![Top 10 Nodes by Degree Centrality]({net_image_paths[11]})

![Histogram of Closeness Centrality]({net_image_paths[12]})

![Top 10 Nodes by Closeness Centrality]({net_image_paths[13]})

![Histogram of Betweenness Centrality]({net_image_paths[14]})

![Top 10 Nodes by Betweenness Centrality]({net_image_paths[15]})

![Histogram of Edge Betweenness Centrality]({net_image_paths[16]})

![Top 10 Edges by Edge Betweenness Centrality]({net_image_paths[17]})

![High Stress Subgraph]({net_image_paths[18]})

![SCC 1]({net_image_paths[19]})

![SCC 2]({net_image_paths[20]})

![SCC 3]({net_image_paths[21]})

![SCC 4]({net_image_paths[22]})

![SCC 5]({net_image_paths[23]})

![KDE - Intersection]({net_image_paths[24]})

![Nearest POI - Biking Distance]({net_image_paths[25]})

## Section 4: Gap Analysis

![Top 10 Connected Components]({gap_image_paths[0]})

![High Low Stress Comoponents]({gap_image_paths[1]})

![Gaps Plot]({gap_image_paths[2]})

![Contact Nodes Plot]({gap_image_paths[3]})

![Heterogeneity of Gap Closure - Benefits]({gap_image_paths[4]})

![Gaps Classified Plot]({gap_image_paths[5]})


## Section 5: Destination Access Analysis

![Hexagonal Grid - Population]({da_image_paths[0]})

![BNA Score Map]({da_image_paths[1]})

"""
if accident_file_exists:
    markdown_content += f"""
## Section 6: Accident Analysis 

![Accident Map]({acc_image_paths[0]})

![Heatmap Map]({acc_image_paths[1]})

![KDE Map]({acc_image_paths[2]})

![Frequency of Accidents by Road type]({acc_image_paths[3]})

![Accidents by Number of Lanes]({acc_image_paths[4]})

![Accidents by MaxSpeed]({acc_image_paths[5]})

![Lanes Speed Distribution]({acc_image_paths[6]})

![Accident by LTS]({acc_image_paths[7]})

![Percentage of Accidents by LTS]({acc_image_paths[8]})

![Number of Accidents by Stress Level]({acc_image_paths[9]})

![Percentage of Accidents by Stress Level]({acc_image_paths[10]})

![Number of Accidents by LTS Value - Intersections]({acc_image_paths[11]})

![Percentage of Accidents by LTS Value - Intersections]({acc_image_paths[12]})

![Number of Accidents by Stress Level - Intersections]({acc_image_paths[13]})

![Percentage of Accidents by Stress Level - Intersections]({acc_image_paths[14]})

![DBSCAN Accident Clusters]({acc_image_paths[15]})

![Chropleth Map Accidents]({acc_image_paths[16]})

## Section 7: Sum-Up Analysis

![H3 hexagons risk accidents]({sump_image_paths[1]})

![Gap associated with risks of accidents]({sump_image_paths[0]})

"""
markdown_content += """

"""

# Write the Markdown content to a file
md_file_path = os.path.join(city_img_path, "report.md")
with open(md_file_path, "w") as file:
    file.write(markdown_content)

# Path for the output HTML file
html_file_path = os.path.join(city_img_path, "report.html")

# Path for the css file
css_file_path = os.path.join(code_path, "report.css")

# Command to convert Markdown to HTML using Pandoc
command = f"pandoc -s {md_file_path} -c {css_file_path} -o {html_file_path}"

# Execute the command
subprocess.run(command, shell=True)