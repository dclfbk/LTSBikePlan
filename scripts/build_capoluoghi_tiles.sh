#!/usr/bin/env bash
# One-shot fetch+compute-lts+build_tiles.sh for every capoluogo di
# provincia/città metropolitana/libero consorzio (~107 comuni - see
# scripts/list_capoluoghi.py) - the comuni someone's actually likely to
# view directly (?area=<capoluogo>) or notice first in the italia view,
# so worth refreshing ahead of a full national reprocessing pass (e.g.
# right after an LTS rule change) rather than waiting for
# build_italy_map_comuni_cron.sh to reach them in istat-code order.
#
# NOT incremental/resumable like build_italy_map_comuni_cron.sh - ~107
# comuni is small enough to just do in one run. Reprocesses every
# capoluogo unconditionally, even ones already in comuni_progress.tsv
# (that's the point when re-running after a rule change - it does NOT
# skip comuni already marked done there, unlike the main cron script).
# Still appends to the same comuni_progress.tsv on success, so the main
# cron script's own progress tracking stays accurate either way.
#
# Does NOT rebuild italia_lts.pmtiles or comuni_index.json itself - run
# scripts/build_national_tiles.sh and scripts/build_comuni_index.py by
# hand once this (and/or the rest of a full reprocessing pass) is done,
# same as LTSBP_COMUNI_PARALLEL_JOBS=4 (per-capoluogo work is mostly
# network I/O - osmit-estratti extract, Mapterhorn DEM tiles - see
# build_italy_map_comuni_cron.sh's own comment on this).
#
# LTSBP_CLEANUP_CACHE=0 keeps each capoluogo's .osm.pbf/DEM cache instead
# of deleting it after success (same flag/default as the main cron script).
#
# Usage: LTSBP_COMUNI_PARALLEL_JOBS=4 scripts/build_capoluoghi_tiles.sh [data_dir]
set -uo pipefail  # NOT -e: one capoluogo failing must not kill the whole run

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-${LTSBP_DATA_DIR:-$REPO_ROOT/data}}"
PARALLEL_JOBS="${LTSBP_COMUNI_PARALLEL_JOBS:-4}"
PROGRESS_FILE="$DATA_DIR/_cache/comuni_progress.tsv"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cd "$REPO_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true  # harmless if already active / using a system install

mkdir -p "$(dirname "$PROGRESS_FILE")"
touch "$PROGRESS_FILE"

log "Listing capoluoghi di provincia/città metropolitana..."
mapfile -t LINES < <(PYTHONPATH=code python3 scripts/list_capoluoghi.py)
if [ ${#LINES[@]} -eq 0 ]; then
  log "ERROR: got an empty capoluoghi list, aborting (osmit-estratti/ISTAT registry unreachable?)"
  exit 1
fi
log "${#LINES[@]} capoluoghi to process."

FAILED_FILE="$(mktemp)"
trap 'rm -f "$FAILED_FILE"' EXIT

process_capoluogo() {
  local line="$1"
  local istat name slug
  IFS=$'\t' read -r istat name slug <<< "$line"
  log "--- $name ($slug, istat=$istat) ---"

  if ! PYTHONPATH=code python3 code/cli.py fetch --area "$name" --area-level comune --istat "$istat" --osmit-estratti; then
    log "FAILED (fetch): $name"
    echo "$name" >> "$FAILED_FILE"
    return
  fi
  if ! PYTHONPATH=code python3 code/cli.py compute-lts --area "$name" --area-level comune --istat "$istat" --osmit-estratti; then
    log "FAILED (compute-lts): $name"
    echo "$name" >> "$FAILED_FILE"
    return
  fi

  if [ "${LTSBP_CLEANUP_CACHE:-1}" = "1" ]; then
    PYTHONPATH=code python3 scripts/cleanup_area_cache.py "$name" --area-level comune --istat "$istat" "$DATA_DIR" \
      || log "WARNING: cache cleanup failed for $name (LTS data itself is unaffected)"
  fi

  if ! scripts/build_tiles.sh "$slug" "$DATA_DIR"; then
    log "FAILED (build_tiles): $name"
    echo "$name" >> "$FAILED_FILE"
    return
  fi

  printf '%s\t%s\t%s\n' "$istat" "$slug" "$(date -u +%FT%TZ)" >> "$PROGRESS_FILE"
}
export -f process_capoluogo log
export DATA_DIR PROGRESS_FILE FAILED_FILE LTSBP_CLEANUP_CACHE

printf '%s\n' "${LINES[@]}" | xargs -d '\n' -P "$PARALLEL_JOBS" -I{} bash -c 'process_capoluogo "$@"' _ {}

FAILED_COUNT=$(wc -l < "$FAILED_FILE" | tr -d ' ')
if [ "$FAILED_COUNT" -gt 0 ]; then
  log "Done with $FAILED_COUNT failure(s): $(paste -sd, "$FAILED_FILE")"
else
  log "Done - all ${#LINES[@]} capoluoghi processed successfully."
fi
log "Reminder: italia_lts.pmtiles/comuni_index.json were NOT rebuilt - run scripts/build_national_tiles.sh and python3 scripts/build_comuni_index.py once you're ready."
