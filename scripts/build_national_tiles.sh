#!/usr/bin/env bash
# Merges every area already processed under $DATA_DIR into a single PMTiles
# tileset, for the "one map with everything" viewer entry point
# (web/index.html?area=italia). Complements build_tiles.sh, which builds a
# tileset for one area at a time - rerun this after processing more areas
# to fold them into the merged tileset.
#
# Requires `tippecanoe` and `pmtiles` (https://github.com/protomaps/go-pmtiles)
# on PATH. See build_tiles.sh for why this goes through an intermediate
# .mbtiles before converting to PMTiles.
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
  --maximum-zoom=16 \
  --extend-zooms-if-still-dropping \
  --maximum-tile-bytes=5000000 \
  -l lts \
  --name "LTSBikePlan Italia" \
  --attribution "LTSBikePlan / OpenStreetMap contributors" \
  "${GEOJSON_FILES[@]}"

pmtiles convert --force "$MBTILES" "$OUT_DIR/italia_lts.pmtiles"

# Merge every area's gap-analysis panel data into one list. Each component's
# "id" is already prefixed "<area_slug>:<index>" by
# domain/gap_analysis.py::annotate_gap_components, so concatenating is safe
# - no cross-area id collisions to resolve.
shopt -s nullglob
GAP_JSON_FILES=("$DATA_DIR"/*/*_gap_components.json)
shopt -u nullglob
if [ ${#GAP_JSON_FILES[@]} -gt 0 ]; then
  python3 -c "
import json, sys
merged = []
for path in sys.argv[1:]:
    with open(path) as f:
        merged.extend(json.load(f))
merged.sort(key=lambda c: c['length_km'], reverse=True)
with open('$OUT_DIR/italia_gap_components.json', 'w') as f:
    json.dump(merged, f)
" "${GAP_JSON_FILES[@]}"
fi

echo "Wrote $OUT_DIR/italia_lts.pmtiles"
echo "Open web/index.html?area=italia to view it."
