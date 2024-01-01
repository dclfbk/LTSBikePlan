import rasterio
from rasterio.merge import merge
from rasterio.plot import show
import glob
import os

# Filepaths
dirpath = "/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/"
out_fp = "merged_dem.tif"

# Search criteria for TIFF files
search_criteria = "*.tif"
q = os.path.join(dirpath, search_criteria)

# List all TIFF files in the directory
tiff_files = glob.glob(q)

# Read and merge
src_files_to_mosaic = []
for fp in tiff_files:
    src = rasterio.open(fp)
    src_files_to_mosaic.append(src)

mosaic, out_trans = merge(src_files_to_mosaic)

# Copy metadata
out_meta = src.meta.copy()

# Update metadata
out_meta.update({"driver": "GTiff",
                 "height": mosaic.shape[1],
                 "width": mosaic.shape[2],
                 "transform": out_trans})

# Write the mosaic raster to disk
with rasterio.open(out_fp, "w", **out_meta) as dest:
    dest.write(mosaic)