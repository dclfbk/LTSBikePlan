from __future__ import annotations

import gzip
import math

import pandas as pd
import pmtiles.reader as pmtiles_reader
from mapbox_vector_tile import decode as decode_mvt


# Standard slippy-map tile -> lon/lat bounds. Used to tag every edge with
# an approximate location (its containing z16 tile's own bounds, ~600m
# across at this latitude range) without decoding per-point MVT geometry
# (tile-local pixel coords needing a z/x/y-aware transform back to lon/
# lat) - overkill for what this is used for (build_comuni_interventions.py
# grouping these into a per-street bounding box good enough for a map
# fitBounds() call, not survey-grade precision).
def _tile_bounds(zoom: int, x: int, y: int) -> tuple[float, float, float, float]:
    n = 2.0**zoom
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2.0 * y / n))))
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2.0 * (y + 1) / n))))
    return lon_min, lat_min, lon_max, lat_max

# Reconstructs the same per-edge attribute table compute_lts.py's
# <slug>_all_lts.parquet holds, straight from the already-built
# <slug>_lts.pmtiles - so a comune's raw data/<slug>/ processing output
# (parquet/geojson/nodes, tens to hundreds of MB per comune) can be
# deleted once its tileset is built, without losing the ability to
# (re)generate web/data/italia_comuni_stats.json or a per-comune
# interventions file. The idea: those files were always just a
# convenience export FROM the same edge table that's ALSO baked into the
# tiles as feature properties - reading it back is lossless, not an
# approximation.
#
# Verified 2026-09-04 against still-available raw data for several
# comuni (Acerra, Napoli, Volterra): reconstructed via this module then
# fed through domain/area_statistics.py's own compute_area_statistics
# (unmodified - no parallel/duplicate formula to drift out of sync)
# reproduces every field exactly, down to float rounding noise at the
# single-metre level on multi-thousand-km aggregates (Napoli's LTS-0
# bucket: 2425.989 vs 2425.988 km). The per-street interventions list
# (build_comuni_interventions.py's own grouping/ranking) matched exactly
# too, 30/30 streets, for Acerra.
#
# Why this is lossless despite pmtiles being generalized per zoom level:
# tippecanoe's own feature-inclusion filter for this project keeps EVERY
# edge from minzoom 12 upward regardless of type (only low zooms thin out
# by highway class for rendering performance - see any *_lts.pmtiles'
# `pmtiles show` output, key "generator_options" - `["any", [">=",
# "$zoom", 12], ...]`), and maxzoom here is always >=12. Geometry gets
# simplified/clipped at tile boundaries per zoom tier, but every
# attribute this project reads (length, lts, rule, is_gap_edge, ...) is a
# static per-edge value baked in before tiling, unaffected by that - and
# a single OSM way graph-split into many short edges (u, v, key is
# OSMnx's own edge primary key) rarely straddles more than one z16 tile
# boundary; where it does, dedup below by that key already collapses the
# resulting duplicate tile fragments into one row before any summing
# happens, so double-counting isn't possible either way.
def load_edges_dataframe(pmtiles_path: str) -> pd.DataFrame:
    """Returns one row per unique edge (u, v, key), with every attribute
    property compute_lts.py exports, read from the tileset's own maxzoom
    tier. Raises FileNotFoundError if the path doesn't exist.
    """
    with open(pmtiles_path, "rb") as file_handle:
        get_bytes = pmtiles_reader.MmapSource(file_handle)
        reader = pmtiles_reader.Reader(get_bytes)
        max_zoom = reader.header()["max_zoom"]

        edges_by_key: dict = {}
        for (zoom, x, y), tile_data in pmtiles_reader.all_tiles(get_bytes):
            if zoom != max_zoom:
                continue
            try:
                raw = gzip.decompress(tile_data)
            except OSError:
                raw = tile_data
            layer = decode_mvt(raw).get("lts")
            if not layer:
                continue
            tile_minlon, tile_minlat, tile_maxlon, tile_maxlat = _tile_bounds(zoom, x, y)
            for feature in layer["features"]:
                props = feature["properties"]
                edge_key = (props.get("u"), props.get("v"), props.get("key"))
                # Approximate location, not exact geometry - see module
                # docstring on _tile_bounds. A boundary-crossing edge that
                # lands in more than one tile only keeps whichever tile's
                # bounds this dedup happens to overwrite with last, which
                # only shrinks the eventual per-street bbox slightly
                # (build_comuni_interventions.py's fitBounds call already
                # pads it) - not worth tracking every fragment for.
                props["bbox_minlon"] = tile_minlon
                props["bbox_minlat"] = tile_minlat
                props["bbox_maxlon"] = tile_maxlon
                props["bbox_maxlat"] = tile_maxlat
                edges_by_key[edge_key] = props

    return pd.DataFrame(edges_by_key.values())
