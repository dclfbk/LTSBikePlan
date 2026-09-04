#!/usr/bin/env bash
# Unattended, cron-friendly rebuild of the whole-Italy map: re-fetches +
# recomputes LTS for every Italian provincia (osmit-estratti, ~107 units -
# each covers all its comuni already, the practical granularity for a
# national run instead of ~7900 individual comuni), then rebuilds the
# merged national tileset. web/ is served in place by this same machine,
# so regenerating web/data/ IS publishing - no extra transfer step.
#
# One provincia failing (network hiccup, osmit-estratti timeout) does not
# abort the run - it's logged and skipped, the rest of Italy still gets
# rebuilt. Safe to just re-run next time - fetch/compute-lts always
# overwrite that area's own files, no manual cleanup needed between runs.
#
# fetch's own downloads (each provincia's .osm.pbf extract + DEM mosaic)
# are cached under data/_cache/ *forever* by design (services/osm_pbf_
# service.py, pipeline/fetch.py - no expiry, reused if already present) -
# left alone, a full run leaves ~107 provincia-sized .osm.pbf files on
# disk permanently, so each provincia's .pbf/DEM mosaic is deleted right
# after its compute-lts succeeds by default (via scripts/
# cleanup_area_cache.py). Set LTSBP_CLEANUP_CACHE=0 to keep the cache
# instead, trading disk space for a faster re-run (or a fixed-up single
# provincia) that skips re-downloading.
#
# Usage: scripts/build_italy_map_cron.sh [data_dir]
# Suggested crontab (weekly, off-peak - a full run visits ~107 province,
# budget several hours depending on machine/network - Trento comune alone
# took ~1.5 min for compute-lts, and province are bigger than comuni):
#   0 2 * * 0 /path/to/LTSBikePlan/scripts/build_italy_map_cron.sh >> /var/log/ltsbikeplan_cron.log 2>&1
set -uo pipefail  # NOT -e: one provincia failing must not kill the whole loop

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-${LTSBP_DATA_DIR:-$REPO_ROOT/data}}"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cd "$REPO_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true  # harmless if already active / using a system install

log "Fetching provincia list from osmit-estratti..."
mapfile -t PROVINCE_LINES < <(PYTHONPATH=code python3 scripts/list_province.py)
if [ ${#PROVINCE_LINES[@]} -eq 0 ]; then
  log "ERROR: got an empty provincia list, aborting (osmit-estratti index unreachable?)"
  exit 1
fi
log "${#PROVINCE_LINES[@]} province to process."

FAILED=()
for line in "${PROVINCE_LINES[@]}"; do
  IFS=$'\t' read -r provincia slug <<< "$line"
  log "--- $provincia ($slug) ---"

  if ! PYTHONPATH=code python3 code/cli.py fetch --area "$provincia" --area-level provincia --osmit-estratti; then
    log "FAILED (fetch): $provincia"
    FAILED+=("$provincia")
    continue
  fi
  if ! PYTHONPATH=code python3 code/cli.py compute-lts --area "$provincia" --area-level provincia --osmit-estratti; then
    log "FAILED (compute-lts): $provincia"
    FAILED+=("$provincia")
    continue
  fi

  if [ "${LTSBP_CLEANUP_CACHE:-1}" = "1" ]; then
    PYTHONPATH=code python3 scripts/cleanup_area_cache.py "$provincia" --area-level provincia "$DATA_DIR" \
      || log "WARNING: cache cleanup failed for $provincia (LTS data itself is unaffected)"
  fi

  if ! scripts/build_tiles.sh "$slug" "$DATA_DIR"; then
    log "WARNING: tile build failed for $provincia (LTS data was computed - only its .pmtiles is missing, it'll just be absent from the national tileset until re-run)"
  fi
done

log "Rebuilding merged national tileset..."
# No $DATA_DIR: build_national_tiles.sh's positional argument is web/data
# (which it already defaults to correctly), not the raw data_dir, since
# its 2026-09-04 rewrite - see that script's own header.
scripts/build_national_tiles.sh

if [ ${#FAILED[@]} -gt 0 ]; then
  log "Done with ${#FAILED[@]} failure(s): ${FAILED[*]}"
  exit 1
fi
log "Done, all ${#PROVINCE_LINES[@]} province processed successfully."
