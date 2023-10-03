import os
import requests

def get_autocomplete_suggestions(query):
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': query,
        'format': 'json',
        'limit': 5  # limit to 5 suggestions
    }
    
    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return [place['display_name'] for place in data]
    else:
        return []

def main():
    base_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/code/"
    
    # Get city input from the user
    city = input("Please enter the name of the city: ")
    suggestions = get_autocomplete_suggestions(city)
    
    if suggestions:
        print("Did you mean one of these?")
        for suggestion in suggestions:
            print(suggestion)
        
        # Confirm from user if they meant one of the suggestions
        choice = input("If one of the above is correct, enter it exactly as shown. Otherwise, re-enter your city: ")
        if choice:
            city = choice  # Overwrite city with user's chosen suggestion
    
    # Run download data file with the city/region as an argument from OSM and DEM for slope calculation
    os.system(f"python {base_path}download_data.py \"{city}\"")

    # os.system(f"python {base_path}download_wcs.py \"{city}\"")
    
    # Run LTS calculus using nbconvert without overwriting the original files
    os.system(f"jupyter nbconvert --to notebook --execute {base_path}lts_calculus.ipynb --output {base_path}lts_calculus.ipynb")
    
    # Set the CITY environment variable and run LTS maps
    os.system(f"CITY=\"{city}\" jupyter nbconvert --to notebook --execute {base_path}lts_analysis_map.ipynb --output {base_path}lts_analysis_map.ipynb")
    os.system(f"CITY=\"{city}\" jupyter nbconvert --to notebook --execute {base_path}lts_h3_choropleth_map.ipynb --output {base_path}lts_h3_choropleth_map.ipynb")


if __name__ == "__main__":
    main()
 