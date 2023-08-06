import os

def main():
    base_path = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/code/"
    
    # Run download data file
    os.system(f"python {base_path}download_data.py")
    
    # Run LTS calculus and LTS plot using nbconvert without overwriting the original files
    os.system(f"jupyter nbconvert --to notebook --execute {base_path}lts_calculus.ipynb --output {base_path}lts_calculus.ipynb")
    os.system(f"jupyter nbconvert --to notebook --execute {base_path}lts_plot.ipynb --output {base_path}lts_plot.ipynb")

if __name__ == "__main__":
    main()
