import os

def main():
    base_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/code/"
    
    # Get city input from the user
    city = input("Please enter the name of the city: ")
    
    # Run download data file with the city/region as an argument from OSM and DEM for slope calculation
    os.system(f"python {base_path}download_data.py \"{city}\"")

    # Run download DEM tiff file with the city/region as an argument
    # os.system(f"python {base_path}download_wcs.py \"{city}\"")
    
    # Run LTS calculus using nbconvert without overwriting the original files
    os.system(f"jupyter nbconvert --to notebook --execute {base_path}lts_calculus.ipynb --output {base_path}lts_calculus.ipynb")
    
    # Set the CITY environment variable and run LTS plot
    os.system(f"CITY=\"{city}\" jupyter nbconvert --to notebook --execute {base_path}lts_plot.ipynb --output {base_path}lts_plot.ipynb")

if __name__ == "__main__":
    main()
