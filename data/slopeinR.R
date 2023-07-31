library(dplyr)
library(sf)
library(osmextract)
library(stplanr)



# get the network
iow_osm = oe_get("Isle of Wight", provider = "geofabrik", stringsAsFactors = FALSE, 
                 quiet = FALSE, force_download = TRUE, force_vectortranslate = TRUE) 

head(iow_osm)
typeof(iow_osm)
# filter the major roads
iow_network = iow_osm %>% 
  dplyr::filter(highway %in% c('primary', "primary_link", 'secondary',"secondary_link", 
                               'tertiary', "tertiary_link", "trunk", "trunk_link", 
                               "residential", "cycleway", "living_street", "unclassified", 
                               "motorway", "motorway_link", "pedestrian", "steps", "track")) #remove: "service"

iow_network$group = rnet_group(iow_network)
iow_network_clean = iow_network %>% filter(group == 1) # the network with more connected segments