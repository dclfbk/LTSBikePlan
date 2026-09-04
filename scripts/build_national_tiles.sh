#!/usr/bin/env bash
# Merges every comune's already-built web/data/<slug>_lts.pmtiles into a
# single national overview tileset (web/data/italia_lts.pmtiles), for the
# "one map with everything" viewer entry point (web/index.html?area=italia).
#
# Rewritten 2026-09-04 to merge the per-comune PMTiles directly via
# tile-join, instead of re-deriving the whole country from raw
# data/<slug>/*_all_lts.geojson (the previous approach, kept below in git
# history if it's ever needed again). That approach quietly broke once
# the comuni cron script started deleting data/<slug>/ entirely after a
# comune's own tiles are built (to reclaim disk on a space-constrained
# server) rather than just its .geojson: this script would then only find
# raw output for the handful of comuni not yet cleaned up, silently
# producing a tiny, geographically incomplete italia_lts.pmtiles (caught
# live 2026-09-04: 13MB, missing Sicily/Calabria/most of the country -
# not an error, just wrong, since the script only checks "did I find at
# least one area" not "did I find all of them").
#
# Why merging pre-built per-comune tiles is lossless for a z4-11 national
# overview (NOT true in general for merging tiles instead of re-tiling -
# it works here specifically because of how build_tiles.sh already
# builds each comune's own pmtiles): build_tiles.sh applies the exact
# same zoom-tiered major-roads-only filter to every comune's own z4-11
# tiles that this script used to apply itself when tiling from raw
# GeoJSON (motorway/trunk only at z4-5, +primary from z6, +secondary from
# z7, everything from z12 - MAJOR_ROADS_FILTER below, kept textually
# identical to build_tiles.sh's own so the two can't silently drift
# apart). tile-join doesn't re-tile, re-simplify, or re-run that filter -
# it just concatenates each input's EXISTING tiles at the requested zoom
# range into one output. Since every comune already carries correctly
# zoom-tiered content at z4-11, and nothing at that generalized an
# overview needs cross-comune knowledge (unlike street-level detail,
# nothing here straddles a comune boundary in a way that would need
# reprocessing together), concatenating is exactly the right operation,
# not an approximation.
#
# Verified 2026-09-04: merging all 7894 comuni this way took well under a
# minute end-to-end (tile-join + pmtiles convert), against the old
# approach's 1-3+ hours regenerating GeoJSON per batch - and produced a
# 144.8MB pmtiles with correct national bounds (lat 35.5-47.1, lon
# 6.7-18.5 - all of Italy including Sicily and the islands), comfortably
# under Cloudflare's free-plan 512MB per-file edge-cache ceiling that
# motivated z11/property-stripping in the first place (see git history
# for the original measurements: a full z16 whole-Italy tileset ran
# 23.6GB).
#
# -y equivalent (--include=lts/highway/rule below): keeps ONLY these 3
# properties in italia_lts.pmtiles, dropping name/comune/length/
# centrality/is_gap_edge/message/... - everything web/app.js's rendering
# of the "italia" source doesn't read (colour+width need "lts", the
# facility dash pattern needs "highway"/"rule"). Safe specifically because
# nothing interactive ever runs against this tileset: web/app.js's
# MIN_CLICK_ZOOM (13) is kept >= COMUNE_SWAP_MIN_ZOOM (12, where this
# tileset's own lts-lines/gap-edges layers already stop rendering), so a
# click, the gap list, and the PDF area-label lookup always hit a
# per-comune source instead, which still carries the full property set.
# If web/app.js ever reads a new property off the "italia" source
# directly, it has to be added here too, or it'll silently be missing.
#
# No more batching/parallel-batches env vars (LTSBP_NATIONAL_BATCH_MAX_MB/
# LTSBP_NATIONAL_PARALLEL_BATCHES from the old GeoJSON-based approach) -
# tile-join's single pass over all 7894 comuni already finishes in
# seconds, nothing here is slow enough to need chunking or concurrency.
#
# Requires `tile-join` and `pmtiles` (https://github.com/protomaps/go-pmtiles)
# on PATH.
#
# Usage: scripts/build_national_tiles.sh [web_data_dir]
#   (web_data_dir defaults to web/data under the repo root - only used to
#   find <slug>_lts.pmtiles and to write the merged italia_lts.pmtiles;
#   unlike the old version, this has nothing to do with the raw data_dir
#   used by fetch/compute-lts)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DATA_DIR="${1:-$REPO_ROOT/web/data}"

command -v tile-join >/dev/null || { echo "tile-join not found on PATH (ships with tippecanoe)" >&2; exit 1; }
command -v pmtiles >/dev/null || { echo "pmtiles (go-pmtiles) not found on PATH" >&2; exit 1; }

shopt -s nullglob
ALL_PMTILES=("$WEB_DATA_DIR"/*_lts.pmtiles)
shopt -u nullglob

# Excludes italia_lts.pmtiles itself (this script's own previous output) -
# tile-join would otherwise happily fold yesterday's national tileset
# back into today's. Harmless (same 3 properties, same zoom range) but
# pointless extra input.
INPUTS=()
for f in "${ALL_PMTILES[@]}"; do
  [ "$(basename "$f")" = "italia_lts.pmtiles" ] && continue
  INPUTS+=("$f")
done

if [ ${#INPUTS[@]} -eq 0 ]; then
  echo "No <slug>_lts.pmtiles found under $WEB_DATA_DIR - build at least one comune's tiles first (scripts/build_tiles.sh)." >&2
  exit 1
fi

echo "Merging ${#INPUTS[@]} comuni's pmtiles into the national overview..."

TMPDIR_RUN="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_RUN"' EXIT

INPUTS_FILE="$TMPDIR_RUN/inputs.txt"
printf '%s\n' "${INPUTS[@]}" > "$INPUTS_FILE"

MBTILES="$TMPDIR_RUN/italia.mbtiles"
tile-join \
  --output="$MBTILES" --force \
  --maximum-zoom=11 --minimum-zoom=4 \
  --include=lts --include=highway --include=rule \
  --no-tile-size-limit \
  --name "LTSBikePlan Italia" \
  --attribution "LTSBikePlan / OpenStreetMap contributors" \
  --read-from="$INPUTS_FILE"

echo "Converting to PMTiles..."
pmtiles convert --force "$MBTILES" "$WEB_DATA_DIR/italia_lts.pmtiles"

echo "Wrote $WEB_DATA_DIR/italia_lts.pmtiles"
echo "Open web/index.html?area=italia to view it."
