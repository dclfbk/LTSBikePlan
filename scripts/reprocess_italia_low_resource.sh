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
# Also wipes data/_cache/mapterhorn_tiles/ (the raw DEM tile cache) once
# per PROVINCIA by default (LTSBP_CLEAN_MAPTERHORN_TILES=1) - normally left
# alone entirely (cleanup_area_cache.py deliberately skips it: it's
# shared/reused across adjacent comuni, see that script's own docstring),
# but at an 8GB disk budget for a full-Italy run, that reuse is exactly
# what makes it grow unboundedly instead of staying flat. Per-provincia
# (not per-comune) keeps most of the actual benefit of that sharing -
# comuni in the same provincia are geographically close and likely to
# reuse the same DEM tiles as each other - while still resetting
# regularly instead of accumulating for all ~7893 comuni. Set
# LTSBP_CLEAN_MAPTERHORN_TILES=0 to go back to the normal, never-cleaned
# shared-cache behaviour (faster still, but unbounded - watch it via
# log_disk_usage below and stop before it eats the 8GB budget).
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
#   scripts/reprocess_italia_low_resource.sh [--resume] [--from PROV_CODE] [prov_istat_code ...]
# With no provincia codes given, processes every provincia/città
# metropolitana known to osmit-estratti's index, in that index's own
# sorted order (numeric on the zero-padded 3-digit code, e.g.
# 001, 002, ... 019, 021, 022, ...). Pass one or more explicit codes to do
# a specific subset instead, same codes calcola.sh already has commented
# in per province:
#   scripts/reprocess_italia_low_resource.sh 001 021 022
#
# --from PROV_CODE processes every provincia from that code onwards in the
# same sorted order, instead of a hand-picked subset - for "pick back up
# partway through the full list" without pasting in every remaining code
# by hand (and without needing --resume, which skips at COMUNE
# granularity based on what's actually finished - --from just changes
# which provincia the loop starts at, whether or not any comune in the
# skipped provincia was actually completed):
#   scripts/reprocess_italia_low_resource.sh --from 004
# Mutually exclusive with passing explicit provincia codes - combine
# --resume and --from freely, but not --from and an explicit code list.
#
# Safe to Ctrl-C: reprocess_comune.sh's own fetch/compute-lts calls are
# idempotent (they just recompute), and this script only ever deletes
# data/<slug>/'s raw files for a comune AFTER confirming its web/data
# outputs were actually refreshed THIS run (see the -nt check below) - so
# an interrupted comune is retried from scratch, never left half-cleaned.
#
# Re-running from scratch (no --resume) WILL redo every comune again, even
# ones a previous run already finished - correct when the reason you're
# running this at all is "the LTS rules changed, everyone needs fresh
# numbers", but wasteful if you're just picking back up after stopping the
# same pass partway through. Pass --resume to skip any comune already
# recorded in $DATA_DIR/_cache/comuni_progress.tsv (istat<TAB>slug<TAB>
# timestamp, one line per success - same file/format
# build_italy_map_comuni_cron.sh's own incremental run uses, so the two
# scripts share one "is this comune's data current" record; just don't run
# them at the same time, see below). Every successful comune is appended
# there regardless of --resume, so a plain run today still lets you
# --resume it tomorrow if it gets interrupted.
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
#     after every provincia instead of leaving it as a shared cache. See
#     the note above - set to 0 to keep the normal (faster, but unbounded)
#     shared-cache behaviour.
#   LTSBP_JOBS (default 1) - comuni to process concurrently within one
#     provincia, via `xargs -P` (same technique calcola.sh/the cron
#     script's own LTSBP_COMUNI_PARALLEL_JOBS already use). Leave at 1 on
#     the actual 4 CPU/8GB RAM/8GB disk server this script was written
#     for - this is for running the SAME script on a bigger box (e.g. a
#     dev laptop with real headroom) where the sequential default just
#     wastes cores. check_disk_or_abort's hard stop still works under
#     parallel jobs (a sentinel file every worker checks before starting
#     its own next comune, not a plain `exit` - that would only kill one
#     xargs slot, not the whole run) but wait_for_memory's per-worker wait
#     loop is now that many workers independently polling/waiting at once,
#     which is a cruder signal than the sequential case - don't set this
#     so high that LTSBP_MIN_FREE_MEM_MB stops meaning anything.
set -uo pipefail  # NOT -e: one comune (or one provincia) failing must not kill the whole run

RESUME=0
FROM_CODE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --resume)
      RESUME=1
      shift
      ;;
    --from)
      FROM_CODE="${2:?usage: --from PROV_CODE}"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

if [ -n "$FROM_CODE" ] && [ "$#" -gt 0 ]; then
  echo "--from and an explicit provincia code list are mutually exclusive (got --from $FROM_CODE plus: $*)" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${LTSBP_DATA_DIR:-$REPO_ROOT/data}"
MIN_FREE_DISK_MB="${LTSBP_MIN_FREE_DISK_MB:-1024}"
MIN_FREE_MEM_MB="${LTSBP_MIN_FREE_MEM_MB:-512}"
MEM_WAIT_RETRY_S="${LTSBP_MEM_WAIT_RETRY_S:-10}"
MEM_WAIT_MAX_RETRIES="${LTSBP_MEM_WAIT_MAX_RETRIES:-12}"  # 12*10s = 2min max wait
CLEAN_MAPTERHORN_TILES="${LTSBP_CLEAN_MAPTERHORN_TILES:-1}"
JOBS="${LTSBP_JOBS:-1}"
PROGRESS_FILE="$DATA_DIR/_cache/comuni_progress.tsv"
ABORT_SENTINEL="$DATA_DIR/_cache/.reprocess_italia_abort"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cd "$REPO_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

mkdir -p "$(dirname "$PROGRESS_FILE")"
touch "$PROGRESS_FILE"
rm -f "$ABORT_SENTINEL"  # clear any stale sentinel left by a previous aborted run
if [ "$RESUME" = "1" ]; then
  log "--resume: $(wc -l < "$PROGRESS_FILE" | tr -d ' ') comuni already marked done in $PROGRESS_FILE will be skipped."
fi

# Checks $PROGRESS_FILE directly (not an in-memory set) - an associative
# array can't be exported to the xargs -P subshells LTSBP_JOBS>1 spawns
# below (bash doesn't support exporting arrays across processes, only
# scalars and functions), so this needs to work identically whether
# called from the sequential loop or a parallel worker. A grep per comune
# is negligible next to the actual fetch/compute-lts work it's gating.
is_already_done() {
  # Anchored at line start so istat "037006" can't false-match a line
  # whose istat merely CONTAINS it (e.g. "1037006") - istat codes are
  # digits only, safe to use unescaped in this basic regex.
  grep -q "^$1"$'\t' "$PROGRESS_FILE"
}
export -f is_already_done

free_disk_mb() { df -Pm "$DATA_DIR" | awk 'NR==2 {print $4}'; }
free_mem_mb() { free -m | awk '/^Mem:/ {print $7}'; }  # "available", not "free" - counts reclaimable cache

log_disk_usage() {
  local free_mb mapterhorn_size data_size web_data_size
  free_mb=$(free_disk_mb)
  mapterhorn_size=$(du -sh "$DATA_DIR/_cache/mapterhorn_tiles" 2>/dev/null | cut -f1)
  data_size=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
  web_data_size=$(du -sh "$REPO_ROOT/web/data" 2>/dev/null | cut -f1)
  local mtk_note="shared, not cleaned"
  [ "$CLEAN_MAPTERHORN_TILES" = "1" ] && mtk_note="wiped after each provincia"
  log "disk: ${free_mb}MB free | data/=${data_size:-?} (mapterhorn_tiles cache=${mapterhorn_size:-?}, $mtk_note) | web/data=${web_data_size:-?}"
}

# Writes $ABORT_SENTINEL and exits THIS process. Under LTSBP_JOBS=1 that's
# the whole script - under LTSBP_JOBS>1 each comune runs in its own xargs
# subshell, so a plain `exit` here would only kill that one worker; the
# sentinel file is what every worker (see process_comune's own check
# below) and the outer per-provincia loop actually watch to stop
# EVERYTHING, not just the worker that happened to notice first.
check_disk_or_abort() {
  local free_mb
  free_mb=$(free_disk_mb)
  if [ "$free_mb" -lt "$MIN_FREE_DISK_MB" ]; then
    log "ABORT: only ${free_mb}MB free on $DATA_DIR's filesystem (threshold: ${MIN_FREE_DISK_MB}MB). Stopping before starting another comune - everything processed so far is intact."
    touch "$ABORT_SENTINEL"
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

# Wipes the raw DEM tile cache - called once per provincia (not per
# comune, see LTSBP_CLEAN_MAPTERHORN_TILES above for why). Safe to delete
# outright (not per-area-selective): tiles are named {zoom}_{x}_{y}.webp
# with no per-area association recorded anywhere, and services/
# dem_service.py::MapterhornDemService re-downloads on demand, writing via
# a temp-file-then-rename (safe even if this ran concurrently with another
# process using the cache - it isn't here, this script is sequential, but
# that's what makes a plain `rm` safe rather than needing to coordinate
# with anything).
clean_mapterhorn_tiles() {
  [ "$CLEAN_MAPTERHORN_TILES" = "1" ] || return 0
  rm -rf "${DATA_DIR:?}/_cache/mapterhorn_tiles"
}

process_comune() {
  local istat="$1" name="$2" slug="$3"
  local pmtiles="$REPO_ROOT/web/data/${slug}_lts.pmtiles"
  local routing_bin="$REPO_ROOT/web/data/${slug}_routing.bin"
  local marker

  if [ -f "$ABORT_SENTINEL" ]; then
    log "SKIP: $name ($slug) - aborting (disk threshold hit earlier), not starting new work"
    return 1
  fi

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
    printf '%s\t%s\t%s\n' "$istat" "$slug" "$(date -u +%FT%TZ)" >> "$PROGRESS_FILE"
    rm -f "$marker"
    return 0
  fi

  log "WARNING: $name ($slug) - web/data outputs missing or not refreshed this run, NOT deleting data/$slug/ raw files"
  rm -f "$marker"
  return 1
}

# Shared by both the sequential loop and the LTSBP_JOBS>1 xargs path:
# parses one "istat<TAB>name<TAB>slug" line, applies --resume skipping,
# calls process_comune, and records a failure to $FAILED_FILE (a plain
# shell array can't be shared back from xargs -P's separate subshells -
# same technique build_italy_map_comuni_cron.sh's own parallel path uses).
process_comune_line() {
  local line="$1" istat name slug
  IFS=$'\t' read -r istat name slug <<< "$line"
  if [ "$RESUME" = "1" ] && is_already_done "$istat"; then
    log "--- $name ($slug, istat=$istat) - already done, --resume skipping ---"
    return 0
  fi
  log "--- $name ($slug, istat=$istat) ---"
  if ! process_comune "$istat" "$name" "$slug"; then
    echo "$name" >> "$FAILED_FILE"
  fi
  log_disk_usage
}
export -f process_comune_line process_comune check_disk_or_abort wait_for_memory trim_comune_data log free_disk_mb free_mem_mb log_disk_usage
export DATA_DIR REPO_ROOT MIN_FREE_DISK_MB MIN_FREE_MEM_MB MEM_WAIT_RETRY_S MEM_WAIT_MAX_RETRIES CLEAN_MAPTERHORN_TILES PROGRESS_FILE ABORT_SENTINEL RESUME

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

if [ -n "$FROM_CODE" ]; then
  FILTERED=()
  for code in "${PROVINCE_CODES[@]}"; do
    # Plain string comparison, not arithmetic - codes are fixed-width
    # zero-padded (e.g. "004"), so lexicographic order matches numeric
    # order here (get_all_province_codes already sorts them the same way).
    [[ "$code" > "$FROM_CODE" || "$code" == "$FROM_CODE" ]] && FILTERED+=("$code")
  done
  log "--from $FROM_CODE: ${#FILTERED[@]} of ${#PROVINCE_CODES[@]} provincia kept."
  PROVINCE_CODES=("${FILTERED[@]}")
fi
log "${#PROVINCE_CODES[@]} provincia/città metropolitana to process."

TOTAL_FAILED=()
for prov_istat in "${PROVINCE_CODES[@]}"; do
  if [ -f "$ABORT_SENTINEL" ]; then
    log "Abort sentinel present - stopping before provincia $prov_istat."
    break
  fi

  mapfile -t COMUNI < <(PYTHONPATH=code python3 scripts/list_comuni_for_provincia.py "$prov_istat")
  if [ ${#COMUNI[@]} -eq 0 ]; then
    log "WARNING: no comuni found for prov_istat_code=$prov_istat - skipping"
    continue
  fi
  log "=== Provincia $prov_istat: ${#COMUNI[@]} comuni (LTSBP_JOBS=$JOBS) ==="

  FAILED_FILE="$(mktemp)"
  export FAILED_FILE  # visible to process_comune_line inside xargs -P's subshells
  if [ "$JOBS" -le 1 ]; then
    for line in "${COMUNI[@]}"; do
      process_comune_line "$line"
    done
  else
    # Same `xargs -d '\n' -P` technique calcola.sh/the incremental cron
    # script already use - -d '\n' (not xargs' default whitespace split)
    # so a comune name with spaces ("Lampedusa e Linosa") stays one
    # argument.
    printf '%s\n' "${COMUNI[@]}" | xargs -d '\n' -P "$JOBS" -I{} bash -c 'process_comune_line "$@"' _ {}
  fi
  while IFS= read -r failed_name; do
    [ -n "$failed_name" ] && TOTAL_FAILED+=("$failed_name ($prov_istat)")
  done < "$FAILED_FILE"
  rm -f "$FAILED_FILE"

  clean_mapterhorn_tiles
  log "Provincia $prov_istat done. Rebuilding merged national tileset + comuni index..."
  scripts/build_national_tiles.sh || log "WARNING: national tileset rebuild failed after provincia $prov_istat"
  python3 scripts/build_comuni_index.py "$DATA_DIR" || log "WARNING: comuni_index.json rebuild failed after provincia $prov_istat"
done

if [ -f "$ABORT_SENTINEL" ]; then
  log "Stopped early: disk space threshold was hit (see the ABORT line above). Free up space and re-run with --resume to continue."
  exit 1
fi

if [ ${#TOTAL_FAILED[@]} -gt 0 ]; then
  log "Done with ${#TOTAL_FAILED[@]} failure(s): $(IFS=,; echo "${TOTAL_FAILED[*]}")"
  exit 1
fi
log "Done - all ${#PROVINCE_CODES[@]} provincia processed successfully."
