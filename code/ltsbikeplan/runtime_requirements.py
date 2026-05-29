from __future__ import annotations


MANUAL_REQUIRED_INPUTS = [
    {
        "name": "DEM raster",
        "env_var": "LTSBP_DEM_PATH",
        "default_path": "data/w51075_s10.tif",
        "required_for": ["fetch", "run", "run-full"],
    }
]

MANUAL_OPTIONAL_INPUTS = [
    {
        "name": "Accidents GeoJSON",
        "path_pattern": "data/accidents_<city>.geojson",
        "required_for": ["report (accident sections)", "future accident module"],
    },
    {
        "name": "Population / destination layers",
        "path_pattern": "data/*population* / data/*hex* / data/*destinations*",
        "required_for": ["run-full destination access and sum-up modules"],
    },
]
