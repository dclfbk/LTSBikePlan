#!/usr/bin/env bash
# Merges every area already processed under $DATA_DIR into a single PMTiles
# tileset, for the "one map with everything" viewer entry point
# (web/index.html?area=italia). Complements build_tiles.sh, which builds a
# tileset for one area at a time - rerun this after processing more areas
# to fold them into the merged tileset.
#
# Requires `tippecanoe` and `pmtiles` (https://github.com/protomaps/go-pmtiles)
# on PATH. See build_tiles.sh for why this goes through an intermediate
# .mbtiles before converting to PMTiles, and for why --minimum-zoom=4 below
# (the map's own MAX_BOUNDS clamp never lets a user zoom out far enough to
# reach z0-3, so building them is wasted time/size - matters even more here
# than per-area, since this tippecanoe run covers all of Italy at once).
#
# --drop-densest-as-needed: unlike build_tiles.sh (deliberately WITHOUT it,
# see that file for why), the merged national tileset needs it - confirmed
# live merging ~50 Sicilian comuni (2M+ features): a single low-zoom tile
# (5/17/12, one covering a wide swath of Sicily) exceeded tippecanoe's
# hard 200000-features-per-tile cap, which has no size-based fallback -
# tippecanoe just stopped emitting any zoom past the last one that fit
# ("TILES ONLY COMPLETE THROUGH ZOOM 4" - the resulting pmtiles had no
# street-level detail anywhere). At the low/regional zooms where this cap
# can even be hit, thinning out density is the correct behaviour (nobody's
# reading individual street segments at a whole-Italy overview zoom) -
# --extend-zooms-if-still-dropping (already present below) is specifically
# meant to pair with a dropping option like this one.
#
# Usage: scripts/build_national_tiles.sh [data_dir]
set -euo pipefail

DATA_DIR="${1:-${LTSBP_DATA_DIR:-data}}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/web/data"
MBTILES="$(mktemp --suffix=.mbtiles)"
trap 'rm -f "$MBTILES"' EXIT

shopt -s nullglob
GEOJSON_FILES=("$DATA_DIR"/*/*_all_lts.geojson)
shopt -u nullglob

if [ ${#GEOJSON_FILES[@]} -eq 0 ]; then
  echo "No *_all_lts.geojson found under $DATA_DIR - run 'ltsbikeplan compute-lts' for at least one area first." >&2
  exit 1
fi

command -v tippecanoe >/dev/null || { echo "tippecanoe not found on PATH" >&2; exit 1; }
command -v pmtiles >/dev/null || { echo "pmtiles (go-pmtiles) not found on PATH" >&2; exit 1; }

mkdir -p "$OUT_DIR"

echo "Merging ${#GEOJSON_FILES[@]} area(s) into one tileset:"
printf '  %s\n' "${GEOJSON_FILES[@]}"

tippecanoe \
  -o "$MBTILES" \
  --force \
  --minimum-zoom=4 \
  --maximum-zoom=16 \
  --extend-zooms-if-still-dropping \
  --drop-densest-as-needed \
  --maximum-tile-bytes=5000000 \
  -l lts \
  --name "LTSBikePlan Italia" \
  --attribution "LTSBikePlan / OpenStreetMap contributors" \
  "${GEOJSON_FILES[@]}"

pmtiles convert --force "$MBTILES" "$OUT_DIR/italia_lts.pmtiles"

echo "Wrote $OUT_DIR/italia_lts.pmtiles"
echo "Open web/index.html?area=italia to view it."
