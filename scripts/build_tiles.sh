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
# --minimum-zoom=4: the map's own MAX_BOUNDS clamp (web/app.js, roughly the
# Azores to the Urals) never lets a user zoom out far enough to hit z0-3
# anyway, so tippecanoe generating those levels is pure wasted build time
# and pmtiles size, not a real zoom range.
#
# Usage: scripts/build_tiles.sh <area_slug> [data_dir]
set -euo pipefail

AREA_SLUG="${1:?Usage: build_tiles.sh <area_slug> [data_dir]}"
DATA_DIR="${2:-${LTSBP_DATA_DIR:-data}}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GEOJSON="$DATA_DIR/$AREA_SLUG/${AREA_SLUG}_all_lts.geojson"
OUT_DIR="$REPO_ROOT/web/data"
MBTILES="$(mktemp --suffix=.mbtiles)"
trap 'rm -f "$MBTILES"' EXIT

if [ ! -f "$GEOJSON" ]; then
  echo "Missing $GEOJSON - run 'ltsbikeplan compute-lts --area \"$AREA_SLUG\"' first." >&2
  exit 1
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
  -l lts \
  --name "${AREA_SLUG} LTS" \
  --attribution "LTSBikePlan / OpenStreetMap contributors" \
  "$GEOJSON"

pmtiles convert --force "$MBTILES" "$OUT_DIR/${AREA_SLUG}_lts.pmtiles"

echo "Wrote $OUT_DIR/${AREA_SLUG}_lts.pmtiles"
echo "Open web/index.html?area=${AREA_SLUG} to view it."
