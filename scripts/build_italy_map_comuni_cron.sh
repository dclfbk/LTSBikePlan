#!/usr/bin/env bash
# Incremental, cron-friendly rebuild of the whole-Italy map at COMUNE
# granularity (~7893 units) - supersedes scripts/build_italy_map_cron.sh's
# per-provincia (~107 units) run. Network centrality (domain/network_
# centrality.py) is sampled but still scales with graph size, and a
# province-sized graph made that step impractically slow - a comune-sized
# graph is the "~33s measured on Trento" case the module's own docstring
# assumes.
#
# ~7893 comuni at Trento-comune's ~1.5min+ each would take days in one run,
# so this is INCREMENTAL: progress is tracked in
# data/_cache/comuni_progress.tsv (istat<TAB>slug<TAB>timestamp, one line
# per successfully completed comune). Each invocation only processes the
# next LTSBP_COMUNI_BATCH_SIZE comuni not yet marked done, then rebuilds
# the national tileset from whatever's on disk so far. Re-run on a tight
# schedule (e.g. every 1-2h) to grind through all of Italy over several
# days; once every comune is done, later runs find nothing left to do and
# just rebuild the national tileset.
#
# A comune is only marked done after compute-lts succeeds - a failure
# (network hiccup, osmit-estratti timeout) leaves it unmarked, so it's
# naturally retried on a later run instead of being skipped forever.
#
# Resolves each comune by --istat (not --area name match): a handful of
# comuni share a name (e.g. two are both named "Paterno" - see
# AreaResolver._duplicate_name_slugs), which would otherwise raise
# AmbiguousAreaError.
#
# Per-area cache (each comune's .osm.pbf extract + DEM mosaic) is deleted
# right after its compute-lts succeeds by default - at ~7893 comuni,
# leaving it all on disk forever isn't viable. Set LTSBP_CLEANUP_CACHE=0 to
# keep it instead (trades disk space for not re-downloading on a rerun,
# e.g. useful while iterating locally on a handful of comuni).
#
# LTSBP_COMUNI_PARALLEL_JOBS (default 4) processes that many comuni of the
# batch concurrently via `xargs -P`. Per-comune work is dominated by
# network I/O (osmit-estratti extract download, Mapterhorn DEM tiles) with
# only a slice of it (compute-lts's own graph/centrality work) actually
# CPU-bound, so this isn't just an N-core speedup - measured production
# pace was ~13min/comune serially (11h for 50 comuni), far slower than the
# ~1.5min/comune this script's original estimate assumed, which pointed at
# I/O wait rather than CPU as the bottleneck. Each comune writes to its own
# data/<slug>/ dir and its own .pmtiles, so comuni themselves don't
# collide; the two caches they DO share (DEM tile cache, osmit topojson
# index - see services/dem_service.py and services/area_index_service.py)
# now write via a temp-file-then-rename so concurrent workers racing on
# the same shared tile/index can't corrupt it. Set to 1 to fall back to
# the old strictly-sequential behaviour. Tune against your server's core
# count and, more importantly, don't set it so high that osmit-estratti or
# Mapterhorn starts rate-limiting/erroring you.
#
# Usage: LTSBP_COMUNI_BATCH_SIZE=150 LTSBP_COMUNI_PARALLEL_JOBS=4 scripts/build_italy_map_comuni_cron.sh [data_dir]
# Suggested crontab (every 2h - budget per-batch runtime as roughly
# (BATCH_SIZE / PARALLEL_JOBS) * (comune compute-lts time), much less than
# province). If a batch is consistently getting killed by the systemd
# unit's TimeoutStartSec before finishing, lower LTSBP_COMUNI_BATCH_SIZE -
# the merged national tileset rebuild only runs once the whole batch loop
# returns, so a batch that never finishes never updates the live map:
#   0 */2 * * * /path/to/LTSBikePlan/scripts/build_italy_map_comuni_cron.sh >> /var/log/ltsbikeplan_comuni_cron.log 2>&1
set -uo pipefail  # NOT -e: one comune failing must not kill the whole batch

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-${LTSBP_DATA_DIR:-$REPO_ROOT/data}}"
BATCH_SIZE="${LTSBP_COMUNI_BATCH_SIZE:-150}"
PARALLEL_JOBS="${LTSBP_COMUNI_PARALLEL_JOBS:-4}"
PROGRESS_FILE="$DATA_DIR/_cache/comuni_progress.tsv"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cd "$REPO_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true  # harmless if already active / using a system install

mkdir -p "$(dirname "$PROGRESS_FILE")"
touch "$PROGRESS_FILE"

log "Fetching comuni list from osmit-estratti..."
mapfile -t ALL_LINES < <(PYTHONPATH=code python3 scripts/list_comuni.py)
if [ ${#ALL_LINES[@]} -eq 0 ]; then
  log "ERROR: got an empty comuni list, aborting (osmit-estratti index unreachable?)"
  exit 1
fi
log "${#ALL_LINES[@]} comuni total."

declare -A DONE
DONE_COUNT=0
while IFS=$'\t' read -r istat _slug _ts; do
  if [ -n "$istat" ]; then
    DONE["$istat"]=1
    DONE_COUNT=$((DONE_COUNT + 1))
  fi
done < "$PROGRESS_FILE"

REMAINING=()
for line in "${ALL_LINES[@]}"; do
  IFS=$'\t' read -r istat _name _slug <<< "$line"
  [ -n "${DONE[$istat]:-}" ] && continue
  REMAINING+=("$line")
done
log "${#REMAINING[@]} comuni not yet processed ($DONE_COUNT already done)."

if [ ${#REMAINING[@]} -eq 0 ]; then
  log "All comuni already processed - nothing to do this run."
  exit 0
fi

BATCH=("${REMAINING[@]:0:$BATCH_SIZE}")
log "Processing batch of ${#BATCH[@]} comuni ($PARALLEL_JOBS in parallel)."

# One line per failed comune name - a plain array can't be shared back from
# the parallel workers below (each xargs -P slot is a separate subshell/
# process), so failures are collected via a file instead. $PROGRESS_FILE
# itself doesn't need the same treatment: appends here are short
# (<PIPE_BUF), so concurrent `>>` from multiple workers is already atomic.
FAILED_FILE="$(mktemp)"
trap 'rm -f "$FAILED_FILE"' EXIT

process_comune() {
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
    log "WARNING: tile build failed for $name (LTS data was computed - only its .pmtiles is missing, it'll just be absent from the national tileset until re-run)"
  fi

  # The .geojson is ~25-30x the size of its .parquet twin (measured on real
  # areas) and, once this comune's own tiles are built, nothing reads it
  # again until the next full national rebuild - which regenerates it from
  # the .parquet on demand anyway (scripts/regenerate_geojson.py). At
  # ~7893 comuni, keeping every .geojson permanently doesn't fit on a
  # disk-constrained server; set LTSBP_KEEP_GEOJSON=1 to keep it instead
  # (e.g. while debugging a specific area).
  if [ "${LTSBP_KEEP_GEOJSON:-0}" != "1" ]; then
    parquet="$DATA_DIR/$slug/${slug}_all_lts.parquet"
    geojson="$DATA_DIR/$slug/${slug}_all_lts.geojson"
    if [ -f "$parquet" ] && [ -f "$geojson" ]; then
      rm -f "$geojson"
    fi
  fi

  printf '%s\t%s\t%s\n' "$istat" "$slug" "$(date -u +%FT%TZ)" >> "$PROGRESS_FILE"
}
export -f process_comune log
export DATA_DIR PROGRESS_FILE FAILED_FILE LTSBP_CLEANUP_CACHE LTSBP_KEEP_GEOJSON

# -d '\n' (not the default whitespace splitting) so each BATCH line is
# passed to process_comune whole - comune names contain spaces (e.g.
# "Lampedusa e Linosa") that would otherwise be split into extra args.
printf '%s\n' "${BATCH[@]}" | xargs -d '\n' -P "$PARALLEL_JOBS" -I{} bash -c 'process_comune "$@"' _ {}

log "Rebuilding merged national tileset..."
TILE_BUILD_FAILED=0
if ! scripts/build_national_tiles.sh "$DATA_DIR"; then
  log "ERROR: national tileset rebuild failed - this batch's comuni were processed but web/data/italia_lts.pmtiles was NOT updated"
  TILE_BUILD_FAILED=1
fi

FAILED_COUNT=$(wc -l < "$FAILED_FILE" | tr -d ' ')
if [ "$FAILED_COUNT" -gt 0 ] || [ "$TILE_BUILD_FAILED" -eq 1 ]; then
  if [ "$FAILED_COUNT" -gt 0 ]; then
    log "Done with $FAILED_COUNT failure(s) this batch: $(paste -sd, "$FAILED_FILE")"
  fi
  exit 1
fi
log "Done, ${#BATCH[@]} comuni processed successfully this batch ($(( ${#REMAINING[@]} - ${#BATCH[@]} )) remaining after this run)."
