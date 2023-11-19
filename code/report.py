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
image_names = ["accident_map.html", 
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
               "DBSCAN_accident_clusters_plot.png"]
image_paths = [os.path.join(city_img_path, img) for img in image_names]

accident_file_exists = os.path.exists(os.path.join(base_path, "accidents_trento.geojson"))


# Markdown Content
markdown_content = f"""
# {city_sanitized} - Level of Traffic Stress Bike Planning and Infrastructure Network Analysis for Safe and Accessible Cycling

## Introduction 

Some introductory text here...
"""
if accident_file_exists:
    markdown_content += f"""
## Section 6: Accident Analysis 

![Accident Map]({image_paths[0]})

![Heatmap Map]({image_paths[1]})

![KDE Map]({image_paths[2]})

![Frequency of Accidents by Road type]({image_paths[3]})

![Accidents by Number of Lanes]({image_paths[4]})

![Accidents by MaxSpeed]({image_paths[5]})

![Lanes Speed Distribution]({image_paths[6]})

![Accident by LTS]({image_paths[7]})

![Percentage of Accidents by LTS]({image_paths[8]})

![Number of Accidents by Stress Level]({image_paths[9]})

![Percentage of Accidents by Stress Level]({image_paths[10]})

![Number of Accidents by LTS Value - Intersections]({image_paths[11]})

![Percentage of Accidents by LTS Value - Intersections]({image_paths[12]})

![Number of Accidents by Stress Level - Intersections]({image_paths[13]})

![Percentage of Accidents by Stress Level - Intersections]({image_paths[14]})

![DBSCAN Accident Clusters]({image_paths[15]})
"""
markdown_content += """
## Section 7: Another Section 

## Section 8: Additional Analysis 
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