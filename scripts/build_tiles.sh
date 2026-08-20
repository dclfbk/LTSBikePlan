#!/usr/bin/env bash
# Builds a PMTiles vector tileset for one area's LTS export, for use by
# web/index.html.
#
# Requires `tippecanoe` and `pmtiles` (https://github.com/protomaps/go-pmtiles)
# on PATH. tippecanoe (tested with v1.36.0) writes MBTiles even when told to
# write a .pmtiles file, so this always goes through an intermediate .mbtiles
# and converts it - only newer tippecanoe builds support --output-format=pmtiles
# directly.
#
# --maximum-zoom is explicit (not -zg): tippecanoe's zoom-guessing heuristic
# is tuned for point density and picked z12 for both a tiny comune (Atrani)
# and a full city (Trento, 126k edges) alike - at z12 a street network is
# too coarse and looks pre-simplified even before the browser gets to draw
# it. z16 keeps real street-level geometry at close zoom. Deliberately NOT
# using --drop-densest-as-needed: for a connected road network it drops
# whole segments (visible gaps) to shrink oversized tiles, whereas
# tippecanoe's default line-simplification (reducing vertex precision, not
# removing features) looks far better at the same zoom - verified visually
# on Trento (126k edges): --drop-densest-as-needed left the city looking
# almost empty at the zoom level `fitBounds` lands on.
#
# --maximum-tile-bytes raises tippecanoe's per-tile size cap well above its
# 500KB default. Below that default, a dense tile (Trento's urban core at
# z9-13) gets its coordinate precision reduced step by step ("detail 12,
# 11, 10, ...", visible in tippecanoe's own progress output) until it fits
# - the same fallback used when a tile is still oversized, just triggered
# far more often on a real street network than on typical point/polygon
# data. That precision loss is what read as visibly jagged/blocky lines at
# z13 (reported against a live Trento build). 5MB comfortably covers
# Trento's densest tiles without needing the fallback; revisit upward
# if a larger provincia/regione build still triggers it.
#
# --minimum-zoom=4: web/app.js's lts-lines/gap-edges layers only render
# from MIN_STREETS_ZOOM (4) up - below that, the map shows a "zoom in"
# hint instead and never even requests tiles below it (MapLibre skips
# fetching a source's tiles for zooms with no active layer).
#
# MAJOR_ROADS_FILTER (-j): tiered by zoom, all still below MIN_CLICK_ZOOM
# (an overview scale, never a "look at this one street" scale) except the
# z12 full-detail tier:
#   z4-5:  motorway/trunk only (a whole-Italy/regional view - even the
#          primary network is too dense to read at this scale)
#   z6-11: + primary
#   z7-11: + secondary (unchanged from the original single-tier filter)
#   z12+:  every class (residential/tertiary/unclassified/service/
#          footway/path/cycleway/...)
# Without this, z4 would be illegible (every street segment at once, a
# solid mass of colour) - this filter is what makes starting the whole
# map at z4 (raised to 7 at one point when it was one flat tier down to
# z4, then re-split into tiers here) viable at all: only the sparse
# major-road skeleton renders that low. Every edge is its own feature at
# every zoom it's included in (edges are minimal 2-point segments already
# - nothing left to simplify geometrically, verified: .simplify() removed
# zero vertices at any tested tolerance on real data), so feature *count*
# is what tile weight below z12 is made of - measured 42% of one national
# test tileset's total bytes were z8-12 alone, before any zoom-tiering
# existed. Confirmed on Pachino: 6.46MB -> 4.35MB (-33%) for its (then
# z8-11) filtered tiles, identical z12+. $zoom is a tippecanoe built-in -
# see "Filtering features by attributes" in tippecanoe's own docs for the
# filter expression syntax (Mapbox GL legacy filter spec, not the newer
# expression syntax - tippecanoe rejected ["get"/"literal"]-wrapped
# expressions with "\"!in\" key is not a string" when this was being
# tested).
MAJOR_ROADS_FILTER='{"lts": ["any", [">=", "$zoom", 12], ["all", [">=", "$zoom", 7], ["in", "highway", "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link"]], ["all", [">=", "$zoom", 6], ["in", "highway", "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link"]], ["in", "highway", "motorway", "motorway_link", "trunk", "trunk_link"]]}'
#
# Usage: scripts/build_tiles.sh <area_slug> [data_dir]
set -euo pipefail

AREA_SLUG="${1:?Usage: build_tiles.sh <area_slug> [data_dir]}"
DATA_DIR="${2:-${LTSBP_DATA_DIR:-data}}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GEOJSON="$DATA_DIR/$AREA_SLUG/${AREA_SLUG}_all_lts.geojson"
PARQUET="$DATA_DIR/$AREA_SLUG/${AREA_SLUG}_all_lts.parquet"
OUT_DIR="$REPO_ROOT/web/data"
MBTILES="$(mktemp --suffix=.mbtiles)"
GEOJSON_TMP=""
cleanup() { rm -f "$MBTILES" "$GEOJSON_TMP"; }
trap cleanup EXIT

# The comuni cron script deletes each area's .geojson after its tiles are
# built (disk: it's ~25-30x the size of the .parquet it's regenerated from
# - see scripts/regenerate_geojson.py). tippecanoe needs a real GeoJSON
# file though (no Parquet reader), so if only the .parquet survived,
# regenerate a throwaway .geojson here and clean it up on exit.
if [ ! -f "$GEOJSON" ]; then
  if [ ! -f "$PARQUET" ]; then
    echo "Missing both $GEOJSON and $PARQUET - run 'ltsbikeplan compute-lts --area \"$AREA_SLUG\"' first." >&2
    exit 1
  fi
  GEOJSON_TMP="$(mktemp --suffix=.geojson)"
  PYTHONPATH="$REPO_ROOT/code" python3 "$REPO_ROOT/scripts/regenerate_geojson.py" "$PARQUET" "$GEOJSON_TMP"
  GEOJSON="$GEOJSON_TMP"
fi

command -v tippecanoe >/dev/null || { echo "tippecanoe not found on PATH" >&2; exit 1; }
command -v pmtiles >/dev/null || { echo "pmtiles (go-pmtiles) not found on PATH" >&2; exit 1; }

mkdir -p "$OUT_DIR"

tippecanoe \
  -o "$MBTILES" \
  --force \
  --minimum-zoom=4 \
  --maximum-zoom=16 \
  --extend-zooms-if-still-dropping \
  --maximum-tile-bytes=5000000 \
  -j "$MAJOR_ROADS_FILTER" \
  -l lts \
  --name "${AREA_SLUG} LTS" \
  --attribution "LTSBikePlan / OpenStreetMap contributors" \
  "$GEOJSON"

pmtiles convert --force "$MBTILES" "$OUT_DIR/${AREA_SLUG}_lts.pmtiles"

echo "Wrote $OUT_DIR/${AREA_SLUG}_lts.pmtiles"
echo "Open web/index.html?area=${AREA_SLUG} to view it."
