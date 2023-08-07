import requests
from owslib.util import Authentication
import warnings
from urllib3.exceptions import InsecureRequestWarning
import rasterio

warnings.simplefilter('ignore', InsecureRequestWarning)

auth = Authentication(verify=False)

# The URL to the WCS service
base_url = 'http://tinitaly.pi.ingv.it/TINItaly_1_1/wcs'

# Define the parameters for the GetCoverage request
params = {
    'service': 'WCS',
    'version': '1.0.0',
    'request': 'GetCoverage',
    'coverage': 'tinitaly_dem',
    'bbox': '749950.0,5099950.0,800050.0,5150050.0',
    'crs': 'EPSG:32632',
    'format': 'image/tiff',
    'width': '5010',
    'height': '5010'
}

# Make the GetCoverage request
response = requests.get(base_url, params=params, verify=False)

# Check the first few characters of the response
print(response.text[:500]) 

# Check the content type of the response
print("Content-Type:", response.headers.get('Content-Type'))

# If the content type indicates it's a TIFF, save the response to a file
if response.headers.get('Content-Type') == 'image/tiff':
    dem_path = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/area.tif'
    with open(dem_path, 'wb') as out_file:
        out_file.write(response.content)
else:
    print("The response is not a TIFF file.")
    exit()

dep_path2 = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/data/w51075_s10.tif'

# Investigate the first DEM
with rasterio.open(dem_path) as dem1:
    dem1_bounds = dem1.bounds
    dem1_shape = dem1.shape
    dem1_crs = dem1.crs
    dem1_transform = dem1.transform

# Investigate the second DEM
with rasterio.open(dep_path2) as dem2:
    dem2_bounds = dem2.bounds
    dem2_shape = dem2.shape
    dem2_crs = dem2.crs
    dem2_transform = dem2.transform

# Compare the bounding boxes
if dem1_bounds == dem2_bounds:
    print("The bounding boxes of the two DEMs are the same.")
else:
    print("The bounding boxes of the two DEMs are different.")
    print("\nBounding box of data.tif:", dem1_bounds)
    print("Bounding box of w51O75_s10.tif:", dem2_bounds)

print("\nShape of data.tif:", dem1_shape)
print("CRS of data.tif:", dem1_crs)
print("Transform of data.tif:", dem1_transform)

print("\nShape of w51O75_s10.tif:", dem2_shape)
print("CRS of w51O75_s10.tif:", dem2_crs)
print("Transform of w51O75_s10.tif:", dem2_transform)
print(dem2_bounds)
