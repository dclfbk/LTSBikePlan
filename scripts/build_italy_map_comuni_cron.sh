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
# Usage: LTSBP_COMUNI_BATCH_SIZE=150 LTSBP_CLEANUP_CACHE=1 scripts/build_italy_map_comuni_cron.sh [data_dir]
# Suggested crontab (every 2h - budget per-batch runtime as roughly
# BATCH_SIZE * (comune compute-lts time), much less than province):
#   0 */2 * * * /path/to/LTSBikePlan/scripts/build_italy_map_comuni_cron.sh >> /var/log/ltsbikeplan_comuni_cron.log 2>&1
set -uo pipefail  # NOT -e: one comune failing must not kill the whole batch

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-${LTSBP_DATA_DIR:-$REPO_ROOT/data}}"
BATCH_SIZE="${LTSBP_COMUNI_BATCH_SIZE:-150}"
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
log "Processing batch of ${#BATCH[@]} comuni."

FAILED=()
for line in "${BATCH[@]}"; do
  IFS=$'\t' read -r istat name slug <<< "$line"
  log "--- $name ($slug, istat=$istat) ---"

  if ! PYTHONPATH=code python3 code/cli.py fetch --area "$name" --area-level comune --istat "$istat" --osmit-estratti; then
    log "FAILED (fetch): $name"
    FAILED+=("$name")
    continue
  fi
  if ! PYTHONPATH=code python3 code/cli.py compute-lts --area "$name" --area-level comune --istat "$istat" --osmit-estratti; then
    log "FAILED (compute-lts): $name"
    FAILED+=("$name")
    continue
  fi

  if [ "${LTSBP_CLEANUP_CACHE:-0}" = "1" ]; then
    PYTHONPATH=code python3 scripts/cleanup_area_cache.py "$name" --area-level comune --istat "$istat" "$DATA_DIR" \
      || log "WARNING: cache cleanup failed for $name (LTS data itself is unaffected)"
  fi

  if ! scripts/build_tiles.sh "$slug" "$DATA_DIR"; then
    log "WARNING: tile build failed for $name (LTS data was computed - only its .pmtiles is missing, it'll just be absent from the national tileset until re-run)"
  fi

  printf '%s\t%s\t%s\n' "$istat" "$slug" "$(date -u +%FT%TZ)" >> "$PROGRESS_FILE"
done

log "Rebuilding merged national tileset..."
scripts/build_national_tiles.sh "$DATA_DIR"

if [ ${#FAILED[@]} -gt 0 ]; then
  log "Done with ${#FAILED[@]} failure(s) this batch: ${FAILED[*]}"
  exit 1
fi
log "Done, ${#BATCH[@]} comuni processed successfully this batch ($(( ${#REMAINING[@]} - ${#BATCH[@]} )) remaining after this run)."
