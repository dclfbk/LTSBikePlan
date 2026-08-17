#!/usr/bin/env python3
"""Regenerates one area's `<slug>_all_lts.geojson` from its much smaller
`<slug>_all_lts.parquet` twin (both written from the same GeoDataFrame in
compute_lts.py, see ExportService.write_geoparquet/write_geojson).

Exists so build_tiles.sh/build_national_tiles.sh (tippecanoe needs a real
GeoJSON file, not a Parquet one - tippecanoe has no Parquet reader) can work
from Parquet-only storage: keeping every comune's full-precision .geojson
forever doesn't fit on a disk-constrained server (~25-30x smaller as
Parquet, measured on real areas - e.g. Pachino 22MB geojson vs 816KB
parquet), so the comuni cron script deletes the .geojson right after a
comune's tiles are built and regenerates it here, into a throwaway temp
file, only when a tileset actually needs rebuilding.

The parquet is stored in WORKING_CRS (EPSG:3035, for compute_lts.py's metric
buffer step) - NOT a straight round-trip to the GeoJSON's EPSG:4326, so this
reprojects via the same ExportService.write_geojson tippecanoe/GeoJSON
consumers already get from a freshly-run compute-lts.

Usage: python3 scripts/regenerate_geojson.py <parquet_path> <geojson_out_path>
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))

import geopandas as gpd

from ltsbikeplan.services.export_service import ExportService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet_path")
    parser.add_argument("geojson_out_path")
    args = parser.parse_args()

    gdf = gpd.read_parquet(args.parquet_path)
    ExportService.write_geojson(gdf, args.geojson_out_path)


if __name__ == "__main__":
    main()
