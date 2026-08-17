#!/usr/bin/env bash
# Merges every area already processed under $DATA_DIR into a single PMTiles
# tileset, for the "one map with everything" viewer entry point
# (web/index.html?area=italia). Complements build_tiles.sh, which builds a
# tileset for one area at a time - rerun this after processing more areas
# to fold them into the merged tileset.
#
# Requires `tippecanoe`, `tile-join` and `pmtiles`
# (https://github.com/protomaps/go-pmtiles) on PATH. See build_tiles.sh for
# why this goes through an intermediate .mbtiles before converting to
# PMTiles, and for why --minimum-zoom=4 below (the map's own MAX_BOUNDS
# clamp never lets a user zoom out far enough to reach z0-3, so building
# them is wasted time/size - matters even more here than per-area, since
# this tippecanoe run covers all of Italy at once).
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
# BATCHED BY ESTIMATED SIZE, not by area count: the comuni cron script
# deletes each area's .geojson right after that area's own tiles are
# built, keeping only the much smaller .parquet (see
# scripts/regenerate_geojson.py) - this step still needs every area's full
# GeoJSON as a real file (tippecanoe has no Parquet reader, and a FIFO-
# streaming approach was tried and abandoned - see git history/commit
# message - tippecanoe hangs (kernel state `wait_for_partner`, confirmed
# via /proc, not a guess) once more than one FIFO is given as input at
# once), so any area missing its .geojson gets one regenerated into a
# throwaway temp file. Regenerating ALL of them at once (old behaviour)
# needs roughly as much temp disk as keeping every area's .geojson
# permanently would - not viable on a disk-constrained server. Instead,
# areas are grouped into batches whose *estimated* total GeoJSON size
# stays under LTSBP_NATIONAL_BATCH_MAX_MB (default 1000), each batch is
# tiled separately (its own --drop-densest-as-needed, correct within that
# batch), and the resulting per-batch .mbtiles are combined at the end
# with `tile-join -pk` (verified: -pk is required - without it, tile-join
# silently DROPS any tile over its hardcoded 500KB cap, no degradation
# like tippecanoe's own --maximum-tile-bytes, confirmed by decoding a
# dropped tile and finding it simply absent from the output).
#
# Batching by SIZE rather than a fixed area count matters because area
# size varies enormously - a comune like Roma alone can plausibly be
# larger than hundreds of small comuni combined (Trento, a mid-size city,
# already measured at 254MB of GeoJSON on its own). A fixed-count batch
# could still blow the disk budget if it happens to contain one huge
# comune; by size, a huge comune just ends up alone in its own
# (unavoidably large) batch instead of forcing every batch to be sized
# for the worst case.
#
# GeoJSON size is estimated from the .parquet size without regenerating
# it first (regenerating just to measure would defeat the purpose): ratio
# empirically measured at 26-28.5x across 7 real areas from an island
# village to an actual city (Siracusa) - consistently tight enough to use
# a flat 30x with headroom. Areas that still have a real .geojson (not yet
# cleaned up) use its actual size instead, no estimate needed.
#
# Usage: LTSBP_NATIONAL_BATCH_MAX_MB=1000 scripts/build_national_tiles.sh [data_dir]
set -euo pipefail

DATA_DIR="${1:-${LTSBP_DATA_DIR:-data}}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/web/data"
BATCH_MAX_BYTES=$(( ${LTSBP_NATIONAL_BATCH_MAX_MB:-1000} * 1000 * 1000 ))
PARQUET_TO_GEOJSON_RATIO=30
MBTILES="$(mktemp --suffix=.mbtiles)"
TMP_GEOJSON_FILES=()
BATCH_MBTILES=()
cleanup() { rm -f "$MBTILES" "${TMP_GEOJSON_FILES[@]}" "${BATCH_MBTILES[@]}"; }
trap cleanup EXIT

shopt -s nullglob
EXISTING_GEOJSON=("$DATA_DIR"/*/*_all_lts.geojson)
PARQUET_FILES=("$DATA_DIR"/*/*_all_lts.parquet)
shopt -u nullglob

declare -A GEOJSON_FOR_DIR
for f in "${EXISTING_GEOJSON[@]}"; do
  GEOJSON_FOR_DIR["$(dirname "$f")"]="$f"
done

declare -A PARQUET_FOR_DIR
for f in "${PARQUET_FILES[@]}"; do
  PARQUET_FOR_DIR["$(dirname "$f")"]="$f"
done

# One area_dir per area, whichever source(s) it has.
AREA_DIRS=()
for d in "${!GEOJSON_FOR_DIR[@]}" "${!PARQUET_FOR_DIR[@]}"; do
  AREA_DIRS+=("$d")
done
mapfile -t AREA_DIRS < <(printf '%s\n' "${AREA_DIRS[@]}" | sort -u)

if [ ${#AREA_DIRS[@]} -eq 0 ]; then
  echo "No *_all_lts.geojson or *_all_lts.parquet found under $DATA_DIR - run 'ltsbikeplan compute-lts' for at least one area first." >&2
  exit 1
fi

command -v tippecanoe >/dev/null || { echo "tippecanoe not found on PATH" >&2; exit 1; }
command -v tile-join >/dev/null || { echo "tile-join not found on PATH (ships with tippecanoe)" >&2; exit 1; }
command -v pmtiles >/dev/null || { echo "pmtiles (go-pmtiles) not found on PATH" >&2; exit 1; }

mkdir -p "$OUT_DIR"

# Build batches: each entry is "area_dir<TAB>estimated_bytes".
BATCHES_FILE="$(mktemp)"
TMP_GEOJSON_FILES+=("$BATCHES_FILE")  # piggyback on the same cleanup trap
{
  for d in "${AREA_DIRS[@]}"; do
    if [ -n "${GEOJSON_FOR_DIR[$d]:-}" ]; then
      size=$(stat -c%s "${GEOJSON_FOR_DIR[$d]}")
    else
      pq_size=$(stat -c%s "${PARQUET_FOR_DIR[$d]}")
      size=$(( pq_size * PARQUET_TO_GEOJSON_RATIO ))
    fi
    printf '%s\t%s\n' "$d" "$size"
  done
} > "$BATCHES_FILE"

run_batch() {
  local batch_num="$1"
  shift
  local dirs=("$@")
  [ ${#dirs[@]} -eq 0 ] && return
  local inputs=()
  local batch_tmp=()
  local area_dir slug tmp
  for area_dir in "${dirs[@]}"; do
    slug="$(basename "$area_dir")"
    if [ -n "${GEOJSON_FOR_DIR[$area_dir]:-}" ]; then
      inputs+=("${GEOJSON_FOR_DIR[$area_dir]}")
    else
      tmp="$(mktemp --suffix=.geojson)"
      echo "  Regenerating GeoJSON for $slug from its .parquet..."
      PYTHONPATH="$REPO_ROOT/code" python3 "$REPO_ROOT/scripts/regenerate_geojson.py" "${PARQUET_FOR_DIR[$area_dir]}" "$tmp"
      batch_tmp+=("$tmp")
      inputs+=("$tmp")
    fi
  done

  local batch_mbtiles
  batch_mbtiles="$(mktemp --suffix=".batch${batch_num}.mbtiles")"
  echo "Batch $batch_num: tiling ${#inputs[@]} area(s)..."
  tippecanoe \
    -o "$batch_mbtiles" \
    --force \
    --minimum-zoom=4 \
    --maximum-zoom=16 \
    --extend-zooms-if-still-dropping \
    --drop-densest-as-needed \
    --maximum-tile-bytes=5000000 \
    -l lts \
    --name "LTSBikePlan Italia (batch $batch_num)" \
    --attribution "LTSBikePlan / OpenStreetMap contributors" \
    "${inputs[@]}"

  rm -f "${batch_tmp[@]}"
  BATCH_MBTILES+=("$batch_mbtiles")
}

batch_num=0
batch_dirs=()
batch_bytes=0
while IFS=$'\t' read -r d size; do
  if [ ${#batch_dirs[@]} -gt 0 ] && [ $((batch_bytes + size)) -gt "$BATCH_MAX_BYTES" ]; then
    batch_num=$((batch_num + 1))
    run_batch "$batch_num" "${batch_dirs[@]}"
    batch_dirs=()
    batch_bytes=0
  fi
  batch_dirs+=("$d")
  batch_bytes=$((batch_bytes + size))
done < "$BATCHES_FILE"
if [ ${#batch_dirs[@]} -gt 0 ]; then
  batch_num=$((batch_num + 1))
  run_batch "$batch_num" "${batch_dirs[@]}"
fi

echo "Joining $batch_num batch(es) into the merged tileset..."
tile-join -f -pk -o "$MBTILES" "${BATCH_MBTILES[@]}"

pmtiles convert --force "$MBTILES" "$OUT_DIR/italia_lts.pmtiles"

echo "Wrote $OUT_DIR/italia_lts.pmtiles"
echo "Open web/index.html?area=italia to view it."
