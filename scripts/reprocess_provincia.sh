#!/usr/bin/env bash
# Forces a full re-run of every comune in ONE provincia, via
# scripts/reprocess_comune.sh - for bulk-refreshing a whole area at once
# (e.g. after a pipeline fix, or to bring a region up to the same data
# freshness as one comune already reprocessed by hand) rather than one
# istat at a time.
#
# Stays at comune granularity throughout (never calls cli.py at the
# provincia level) - see scripts/build_italy_map_comuni_cron.sh's own
# comment for why the site moved off provincia-sized batches, and because
# web/data/comuni_index.json's z12+ per-comune swap (build_comuni_index.py)
# only ever looks for individual <slug>_routing.bin/_lts.pmtiles files, not
# a merged provincia one.
#
# Usage: scripts/reprocess_provincia.sh [--patch-index] <prov_istat_code> [data_dir]
#   prov_istat_code - e.g. 021 for Bolzano - Bozen / Alto Adige. Find one:
#     python3 -c "
#     import json
#     d = json.load(open('data/_cache/osmit_index/limits_IT_provinces.json'))
#     for g in d['objects'][list(d['objects'])[0]]['geometries']:
#         print(g['properties']['prov_istat_code'], g['properties']['name'])
#     "
#
# Example (Alto Adige, 116 comuni):
#   scripts/reprocess_provincia.sh 021
#
# Runs LTSBP_SKIP_NATIONAL_REBUILD=1 for every comune (the expensive
# whole-Italy tippecanoe merge would otherwise run once per comune - see
# reprocess_comune.sh's own comment on that flag), then the two rebuild
# steps ONCE at the very end. Sequential, not parallel (unlike the cron
# script's LTSBP_COMUNI_PARALLEL_JOBS) - deliberately gentler on a
# resource-constrained server; comuni already reprocessed successfully are
# NOT retried if a later one in the list fails, matching
# build_italy_map_comuni_cron.sh's own "one failure doesn't kill the
# batch" behaviour (set -uo pipefail, not -e).
#
# --patch-index: skips fetch/compute-lts/tiles/routing-graph AND the two
# rebuild steps entirely - just runs scripts/patch_comuni_index.py for
# this provincia instead. For when the actual data files (_lts.pmtiles/
# _routing.bin) already got onto the server some other way (reported live:
# copied there by hand, same as Palermo earlier this session) and
# comuni_index.json is the only thing still out of date - adds whichever
# of the provincia's comuni aren't indexed yet, flips has_routing to true
# for ones that are (see that script's own docstring). Much cheaper than
# the full path above: no fetch/compute-lts, no tippecanoe.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH_INDEX_ONLY=0
if [ "${1:-}" = "--patch-index" ]; then
  PATCH_INDEX_ONLY=1
  shift
fi
PROV_ISTAT="${1:?usage: reprocess_provincia.sh [--patch-index] <prov_istat_code> [data_dir]}"
DATA_DIR="${2:-${LTSBP_DATA_DIR:-$REPO_ROOT/data}}"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cd "$REPO_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

if [ "$PATCH_INDEX_ONLY" = "1" ]; then
  log "Patching comuni_index.json for provincia $PROV_ISTAT only (no fetch/compute-lts/tiles/routing-graph)..."
  exec python3 scripts/patch_comuni_index.py "$PROV_ISTAT" "$DATA_DIR"
fi

mapfile -t COMUNI < <(PYTHONPATH=code python3 scripts/list_comuni_for_provincia.py "$PROV_ISTAT")
if [ ${#COMUNI[@]} -eq 0 ]; then
  log "ERROR: no comuni found for prov_istat_code=$PROV_ISTAT - aborting"
  exit 1
fi
log "${#COMUNI[@]} comuni found for provincia $PROV_ISTAT."

FAILED=()
i=0
for line in "${COMUNI[@]}"; do
  i=$((i + 1))
  IFS=$'\t' read -r istat name slug <<< "$line"
  log "--- [$i/${#COMUNI[@]}] $name ($slug, istat=$istat) ---"
  if ! LTSBP_SKIP_NATIONAL_REBUILD=1 scripts/reprocess_comune.sh "$slug" "$istat" "$name" "$DATA_DIR"; then
    log "FAILED: $name ($slug)"
    FAILED+=("$name")
  fi
done

log "Rebuilding merged national tileset..."
# No $DATA_DIR: build_national_tiles.sh's positional argument is web/data
# (which it already defaults to correctly), not the raw data_dir, since
# its 2026-09-04 rewrite - see that script's own header.
scripts/build_national_tiles.sh
log "Rebuilding comuni index (istat/slug/bbox/has_routing)..."
python3 scripts/build_comuni_index.py "$DATA_DIR"

if [ ${#FAILED[@]} -gt 0 ]; then
  log "Done with ${#FAILED[@]} failure(s): $(IFS=,; echo "${FAILED[*]}")"
  exit 1
fi
log "Done, all ${#COMUNI[@]} comuni in provincia $PROV_ISTAT processed successfully."
