#!/usr/bin/env bash
# Recomputes all of Italy comune-by-comune, grouped by provincia/città
# metropolitana (same granularity calcola.sh already uses one province at
# a time), written for a resource-constrained server: 4 CPU / 8GB RAM /
# only ~8GB free disk. The two things that make a plain reprocess_provincia.sh
# loop unsafe at that disk budget:
#
#   1. data/<slug>/ keeps its raw .parquet/.geojson/nodes.parquet forever
#      after a comune is done - nothing needs them again once that
#      comune's own web/data/<slug>_lts.pmtiles + _routing.bin exist
#      (build_national_tiles.sh merges already-built .pmtiles files
#      directly, not the raw per-comune data - see its own 2026-09-04
#      rewrite note). A big comune's .geojson alone runs 25-30x its
#      .parquet (Bologna: 348MB vs 13MB, measured) - across ~7893 comuni
#      that's nowhere near 8GB free.
#   2. calcola.sh's `xargs -P 10` (or the cron script's default
#      LTSBP_COMUNI_PARALLEL_JOBS=4) means that many comuni's own
#      .osm.pbf + DEM mosaic + networkx graph are all alive in RAM/disk
#      at once, before any one of them gets to clean up - fine on a big
#      box, not on 8GB RAM / 8GB disk.
#
# This script stays SEQUENTIAL (one comune at a time - see the CPU/RAM
# note below) and, right after each comune's tiles+routing graph are
# confirmed on disk, deletes its data/<slug>/ .geojson/.parquet/
# nodes.parquet - keeping only the tiny <slug>_stats.json (a few KB,
# needed later by scripts/build_comuni_stats.py's aggregation, which globs
# data/*/*_stats.json - deleting it would silently drop that comune from
# the comuni-comparison stats page until recomputed).
#
# Also wipes data/_cache/mapterhorn_tiles/ (the raw DEM tile cache) after
# every comune by default (LTSBP_CLEAN_MAPTERHORN_TILES=1) - normally left
# alone (cleanup_area_cache.py deliberately skips it: it's shared/reused
# across adjacent comuni, see that script's own docstring), but at an 8GB
# disk budget for a full-Italy run, that reuse is exactly what makes it
# grow unboundedly instead of staying flat. Trading disk for network here:
# every comune re-downloads DEM tiles a neighbour may have just fetched a
# minute earlier, instead of the two of them sharing one cached copy. Set
# LTSBP_CLEAN_MAPTERHORN_TILES=0 to go back to the normal shared-cache
# behaviour (faster overall, but the cache then grows for good - watch it
# via log_disk_usage below and stop before it eats the 8GB budget).
#
# CPU/RAM: NOT parallelized on purpose. Per-comune work is mostly network
# I/O (osmit-estratti download, Mapterhorn tiles) with only a slice of it
# (compute-lts's graph/centrality step) actually CPU-bound - see the cron
# script's own comment on why it still defaults to 4 parallel jobs on a
# bigger box. On 4 CPU / 8GB RAM, running several comuni at once means
# several networkx graphs + geopandas frames live simultaneously; a single
# big comune (Milano, Roma) already uses a non-trivial slice of 8GB alone.
# Trade wall-clock time for headroom here - see LTSBP_MIN_FREE_MEM_MB below
# for the one guard this script CAN offer against that.
#
# Usage:
#   scripts/reprocess_italia_low_resource.sh [prov_istat_code ...]
# With no arguments, processes every provincia/città metropolitana known to
# osmit-estratti's index (order as returned by the index - not
# alphabetical). Pass one or more explicit codes to do a subset instead,
# same codes calcola.sh already has commented in per province:
#   scripts/reprocess_italia_low_resource.sh 001 021 022
#
# Safe to Ctrl-C and re-run: reprocess_comune.sh's own fetch/compute-lts
# calls are idempotent (they just recompute), and this script only ever
# deletes data/<slug>/'s raw files for a comune AFTER confirming its
# web/data outputs were actually refreshed THIS run (see the -nt check
# below) - so an interrupted comune is retried from scratch, never left
# half-cleaned.
#
# Do not run this at the same time as the periodic
# build_italy_map_comuni_cron.sh systemd timer (see deploy/) if one is
# configured on this box - both would compete for the same 4 CPU/8GB RAM/
# 8GB disk at once. Pause that timer first.
#
# Env vars:
#   LTSBP_MIN_FREE_DISK_MB (default 1024) - hard abort (whole script, not
#     just the current comune) if free disk on the data dir's filesystem
#     drops below this BEFORE starting a new comune. A comune that fills
#     the disk mid-download/mid-tippecanoe is a worse outcome than
#     stopping cleanly with everything so far intact.
#   LTSBP_MIN_FREE_MEM_MB (default 512) - soft guard: if free+available RAM
#     drops below this before starting a new comune, wait and recheck
#     (LTSBP_MEM_WAIT_RETRY_S apart, up to LTSBP_MEM_WAIT_MAX_RETRIES times)
#     rather than piling another comune's graph on top of whatever's
#     already using memory. Proceeds anyway with a logged warning if still
#     low after the max wait, rather than blocking forever on a reading
#     that may just be temporary page-cache pressure.
#   LTSBP_DATA_DIR (default ./data)
#   LTSBP_CLEAN_MAPTERHORN_TILES (default 1) - wipe data/_cache/mapterhorn_tiles/
#     after every comune instead of leaving it as a shared cache. See the
#     note above - set to 0 to keep the normal (faster, but unbounded)
#     shared-cache behaviour.
set -uo pipefail  # NOT -e: one comune (or one provincia) failing must not kill the whole run

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${LTSBP_DATA_DIR:-$REPO_ROOT/data}"
MIN_FREE_DISK_MB="${LTSBP_MIN_FREE_DISK_MB:-1024}"
MIN_FREE_MEM_MB="${LTSBP_MIN_FREE_MEM_MB:-512}"
MEM_WAIT_RETRY_S="${LTSBP_MEM_WAIT_RETRY_S:-10}"
MEM_WAIT_MAX_RETRIES="${LTSBP_MEM_WAIT_MAX_RETRIES:-12}"  # 12*10s = 2min max wait
CLEAN_MAPTERHORN_TILES="${LTSBP_CLEAN_MAPTERHORN_TILES:-1}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cd "$REPO_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

free_disk_mb() { df -Pm "$DATA_DIR" | awk 'NR==2 {print $4}'; }
free_mem_mb() { free -m | awk '/^Mem:/ {print $7}'; }  # "available", not "free" - counts reclaimable cache

log_disk_usage() {
  local free_mb mapterhorn_size data_size web_data_size
  free_mb=$(free_disk_mb)
  mapterhorn_size=$(du -sh "$DATA_DIR/_cache/mapterhorn_tiles" 2>/dev/null | cut -f1)
  data_size=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
  web_data_size=$(du -sh "$REPO_ROOT/web/data" 2>/dev/null | cut -f1)
  local mtk_note="shared, not cleaned"
  [ "$CLEAN_MAPTERHORN_TILES" = "1" ] && mtk_note="wiped after each comune"
  log "disk: ${free_mb}MB free | data/=${data_size:-?} (mapterhorn_tiles cache=${mapterhorn_size:-?}, $mtk_note) | web/data=${web_data_size:-?}"
}

check_disk_or_abort() {
  local free_mb
  free_mb=$(free_disk_mb)
  if [ "$free_mb" -lt "$MIN_FREE_DISK_MB" ]; then
    log "ABORT: only ${free_mb}MB free on $DATA_DIR's filesystem (threshold: ${MIN_FREE_DISK_MB}MB). Stopping before starting another comune - everything processed so far is intact."
    exit 1
  fi
}

wait_for_memory() {
  local mem_mb tries=0
  mem_mb=$(free_mem_mb)
  while [ "$mem_mb" -lt "$MIN_FREE_MEM_MB" ] && [ "$tries" -lt "$MEM_WAIT_MAX_RETRIES" ]; do
    log "waiting: only ${mem_mb}MB available RAM (threshold: ${MIN_FREE_MEM_MB}MB) - retry $((tries + 1))/$MEM_WAIT_MAX_RETRIES in ${MEM_WAIT_RETRY_S}s"
    sleep "$MEM_WAIT_RETRY_S"
    mem_mb=$(free_mem_mb)
    tries=$((tries + 1))
  done
  if [ "$mem_mb" -lt "$MIN_FREE_MEM_MB" ]; then
    log "WARNING: still only ${mem_mb}MB available RAM after ${MEM_WAIT_MAX_RETRIES} retries - proceeding anyway"
  fi
}

# Deletes a comune's raw data/<slug>/ outputs, but ONLY the ones nothing
# needs again once its web/data/<slug>_lts.pmtiles + _routing.bin exist -
# keeps <slug>_stats.json (tiny; scripts/build_comuni_stats.py's national
# aggregation reads it later).
trim_comune_data() {
  local slug="$1"
  local dir="$DATA_DIR/$slug"
  [ -d "$dir" ] || return 0
  rm -f "$dir/${slug}_all_lts.geojson" "$dir/${slug}_all_lts.parquet" "$dir/${slug}_nodes.parquet" "$dir/gdf_data.pkl"
}

# Wipes the raw DEM tile cache - see LTSBP_CLEAN_MAPTERHORN_TILES above.
# Safe to delete outright (not per-comune-selective): tiles are named
# {zoom}_{x}_{y}.webp with no per-area association recorded anywhere, and
# services/dem_service.py::MapterhornDemService re-downloads on demand,
# writing via a temp-file-then-rename (safe even if this ran concurrently
# with another process using the cache - it isn't here, this script is
# sequential, but that's what makes a plain `rm` safe rather than needing
# to coordinate with anything).
clean_mapterhorn_tiles() {
  [ "$CLEAN_MAPTERHORN_TILES" = "1" ] || return 0
  rm -rf "${DATA_DIR:?}/_cache/mapterhorn_tiles"
}

process_comune() {
  local istat="$1" name="$2" slug="$3"
  local pmtiles="$REPO_ROOT/web/data/${slug}_lts.pmtiles"
  local routing_bin="$REPO_ROOT/web/data/${slug}_routing.bin"
  local marker
  marker="$(mktemp)"

  check_disk_or_abort
  wait_for_memory

  if ! LTSBP_SKIP_NATIONAL_REBUILD=1 scripts/reprocess_comune.sh "$slug" "$istat" "$name" "$DATA_DIR"; then
    log "FAILED: $name ($slug) - reprocess_comune.sh reported an error, leaving data/$slug/ as-is for inspection"
    rm -f "$marker"
    return 1
  fi

  # reprocess_comune.sh has no -e and doesn't propagate a build_tiles.sh/
  # build_routing_graph.py failure to its own exit code (it just logs and
  # moves on - see that script's own comments) - checking file mtimes
  # against a marker created BEFORE this call is the only reliable way to
  # confirm THIS run actually refreshed them, not that they're stale
  # leftovers from a previous comune run. Only once confirmed is it safe
  # to delete data/<slug>/'s raw files below.
  if [ -f "$pmtiles" ] && [ "$pmtiles" -nt "$marker" ] && [ -f "$routing_bin" ] && [ "$routing_bin" -nt "$marker" ]; then
    trim_comune_data "$slug"
    clean_mapterhorn_tiles
    rm -f "$marker"
    return 0
  fi

  log "WARNING: $name ($slug) - web/data outputs missing or not refreshed this run, NOT deleting data/$slug/ raw files"
  rm -f "$marker"
  return 1
}

get_all_province_codes() {
  python3 -c "
import json, os, sys
sys.path.insert(0, os.path.join('$REPO_ROOT', 'code'))
from ltsbikeplan.services.area_index_service import AreaResolver
resolver = AreaResolver(cache_dir='$DATA_DIR')
index_path = os.path.join('$DATA_DIR', '_cache', 'osmit_index', 'limits_IT_provinces.json')
resolver.list_areas('provincia')  # ensures the index file above is cached/downloaded
with open(index_path) as f:
    d = json.load(f)
codes = sorted({g['properties']['prov_istat_code'] for g in d['objects'][list(d['objects'])[0]]['geometries']})
print('\n'.join(codes))
"
}

if [ "$#" -ge 1 ]; then
  PROVINCE_CODES=("$@")
else
  log "No provincia codes given - processing every provincia/città metropolitana known to osmit-estratti's index."
  mapfile -t PROVINCE_CODES < <(get_all_province_codes)
fi
log "${#PROVINCE_CODES[@]} provincia/città metropolitana to process."

TOTAL_FAILED=()
for prov_istat in "${PROVINCE_CODES[@]}"; do
  mapfile -t COMUNI < <(PYTHONPATH=code python3 scripts/list_comuni_for_provincia.py "$prov_istat")
  if [ ${#COMUNI[@]} -eq 0 ]; then
    log "WARNING: no comuni found for prov_istat_code=$prov_istat - skipping"
    continue
  fi
  log "=== Provincia $prov_istat: ${#COMUNI[@]} comuni ==="

  i=0
  for line in "${COMUNI[@]}"; do
    i=$((i + 1))
    IFS=$'\t' read -r istat name slug <<< "$line"
    log "--- [$i/${#COMUNI[@]}] $name ($slug, istat=$istat) - provincia $prov_istat ---"
    if ! process_comune "$istat" "$name" "$slug"; then
      TOTAL_FAILED+=("$name ($prov_istat)")
    fi
    log_disk_usage
  done

  log "Provincia $prov_istat done. Rebuilding merged national tileset + comuni index..."
  scripts/build_national_tiles.sh || log "WARNING: national tileset rebuild failed after provincia $prov_istat"
  python3 scripts/build_comuni_index.py "$DATA_DIR" || log "WARNING: comuni_index.json rebuild failed after provincia $prov_istat"
done

if [ ${#TOTAL_FAILED[@]} -gt 0 ]; then
  log "Done with ${#TOTAL_FAILED[@]} failure(s): $(IFS=,; echo "${TOTAL_FAILED[*]}")"
  exit 1
fi
log "Done - all ${#PROVINCE_CODES[@]} provincia processed successfully."
