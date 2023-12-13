

<div class='blue-stripe-header'>
<h2>Trento - Level of Traffic Stress Bike Planning and Infrastructure Network Analysis for Safe and Accessible Cycling</h2>

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

![Slope Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/slope_map.html)

![Level of Traffic Stress Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/lts_map.html)

![LTS H3 Choropleth map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/choropleth_lts_map.html)

## Section 2: Exploratory Spatial Data Analysis

![City Network](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/network_base.png)

![Street Network Orientation](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/streetnetworkorientation_plot.png)

![Polar Plot](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/sno_polar_plot.png)

## Section 3: Cluster Analysis
![DBSCAN High Stress Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/dbscan_lts_cluster_geo.png)

![DBSCAN High Stress](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/dbscan_lts_cluster.png)

![HDBSCAN High Stress Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/hdbscan_lts_cluster_geo.png)

![HDBSCAN High Stress](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/hdbscan_lts_cluster.png)

![OPTICS High Stress Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/optics_lts_cluster_geo.png)

![OPTICS High Stress](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/optics_lts_cluster.png)

## Section 4: Network Analysis

![Nodes Degree Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/nodes_degree_centrality.png)

![Nodes Closeness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/nodes_closeness_centrality.png)

![Nodes Betweenness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/nodes_betweenness_centrality.png)

![Edges Betweenness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/edge_betweenness_centrality.png)

![LTS Distribution for Nodes](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/lts_distrib_nodes_plot.png)

![LTS Distribution for Edges](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/lts_distrib_edges_plot.png)

![Nodes Degree Centrality weighted by LTS](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/nodess_betweenness_centrality.png)

![Nodes Closeness Centrality weighted by LTS](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/nodess_closeness_centrality.png)

![Nodes Betweenness Centrality weighted by LTS](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/nodess_betweenness_centrality.png)

![Edges Betweenness Centrality weighted by LTS](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/edgez_betweenness_centrality.png)

![Histogram of Degree Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/deg_central_map.png)

![Top 10 Nodes by Degree Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/deg_central_map_top_nodes.png)

![Histogram of Closeness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/clos_central_map.png)

![Top 10 Nodes by Closeness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/clos_central_map_top_nodes.png)

![Histogram of Betweenness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/betw_central_map.png)

![Top 10 Nodes by Betweenness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/betw_central_map_top_nodes.png)

![Histogram of Edge Betweenness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/edge_bet_central_map.png)

![Top 10 Edges by Edge Betweenness Centrality](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/edge_bet_central_map_top_nodes.png)

![High Stress Subgraph](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/g_high_stres_map.png)

![SCC 1](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/component_1.png)

![SCC 2](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/component_2.png)

![SCC 3](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/component_3.png)

![SCC 4](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/component_4.png)

![SCC 5](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/component_5.png)

![KDE - Intersection](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/kde_est_simplifiedgraph.png)

![Nearest POI - Biking Distance](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/nearest_poi_plot.png)

## Section 4: Gap Analysis

![Top 10 Connected Components](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/Top10connectedcomponents_plot.png)

![High Low Stress Comoponents](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/highlowstresscomponents_plot.png)

![Gaps Plot](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/gaps_plot.png)

![Contact Nodes Plot](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/contact_nodes_plot.png)

![Heterogeneity of Gap Closure - Benefits](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/heter_gapclosure_benefits.png)

![Gaps Classified Plot](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/gaps_classified_plot.html)


## Section 5: Destination Access Analysis

![Hexagonal Grid - Population](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/hexagonal_grid_population.html)

![BNA Score Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/bna_score_map.html)


## Section 6: Accident Analysis 

![Accident Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/accident_map.html)

![Heatmap Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/heatmap_map.html)

![KDE Map](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/kde_map.html)

![Frequency of Accidents by Road type](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/frequencyaccidentsbyroads_plot.png)

![Accidents by Number of Lanes](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/accidentsbynumberlanes_plot.png)

![Accidents by MaxSpeed](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/accidentsbymaxspeed_plot.png)

![Lanes Speed Distribution](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/lanes_speed_distribution_plot.png)

![Accident by LTS](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/accidents_lts_plot.png)

![Percentage of Accidents by LTS](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/perc_accidents_lts_plot.png)

![Number of Accidents by Stress Level](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/accidents_stress_level_plot.png)

![Percentage of Accidents by Stress Level](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/perc_accidents_stress_level_plot.png)

![Number of Accidents by LTS Value - Intersections](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/accidents_lts_intersection_plot.png)

![Percentage of Accidents by LTS Value - Intersections](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/perc_accidents_lts_intersection_plot.png)

![Number of Accidents by Stress Level - Intersections](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/accidents_stress_level_intersection_plot.png)

![Percentage of Accidents by Stress Level - Intersections](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/perc_accidents_stress_level_intersection_plot.png)

![DBSCAN Accident Clusters](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/DBSCAN_accident_clusters_plot.png)

![Chropleth Map Accidents](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/choropleth_lts_accidents_map.html)

## Section 7: Sum-Up Analysis

![H3 hexagons risk accidents](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/risk_accidents_hexagon.html)

![Gap associated with risks of accidents](/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/gap_quadrants.html)



