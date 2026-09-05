#!/usr/bin/env bash
# Rebuilds the national comuni/provincia/regione stats and the per-comune
# priority-intervention lists (web/data/italia_*_stats.json,
# web/data/interventions/*.json) from whatever's on disk: raw data/<slug>/
# output where it still exists (fast path), and web/data/<slug>_lts.pmtiles
# for every other comune (services/pmtiles_edges_service.py reconstructs
# the same per-edge table losslessly from the tileset itself - see that
# module's own docstring). This is what makes it safe to delete data/ to
# reclaim disk once a comune's tileset is already built: the stats can
# always be regenerated from web/data/ alone.
#
# LOW PRIORITY BY DESIGN: meant to run on the same small box (4 CPU / 8GB)
# that's also serving nginx for the live site, so it must never compete
# with real traffic for CPU or disk I/O. Every python invocation runs
# under `ionice -c3` (idle I/O class - only gets disk I/O when nothing
# else wants it) and `nice -n 19` (lowest CPU scheduling priority). Each
# step is also single-process/single-threaded (no parallelism to tune
# down), so at most it uses one of the 4 cores at a time, and only when
# the scheduler has nothing higher-priority to run - nginx (or anything
# else on the box) always wins a resource fight against this.
#
# For an even harder guarantee than `nice`/`ionice` give (which only
# affect scheduling priority, not hard caps), and if this server runs
# systemd, wrap the whole script in a resource-capped transient unit
# instead of invoking it directly:
#   systemd-run --scope -p CPUQuota=50% -p MemoryMax=3G --nice=19 \
#     ./scripts/rebuild_stats_from_pmtiles.sh
#
# Takes 1-3 hours for the full ~7900-comune set on modest hardware (most
# comuni are small - a few seconds each; a handful of large cities like
# Roma run tens of seconds). Safe to Ctrl-C and rerun later: every step
# rebuilds its output from scratch each time (not incremental), so an
# interrupted run just means starting over, not corrupted output - the
# national JSON files are only overwritten at the very end of each
# script's own run, never partially written.
#
# Usage: scripts/rebuild_stats_from_pmtiles.sh [data_dir]
#   (data_dir defaults to LTSBP_DATA_DIR or ./data, same as every other
#   script here - only used for the raw-data fast path and the small
#   ISTAT/population caches under <data_dir>/_cache/, safe to point at an
#   empty/nonexistent directory if data/ has been deleted entirely)
#
# To run this unattended on the server, in the background, surviving your
# SSH session ending:
#   nohup ./scripts/rebuild_stats_from_pmtiles.sh > logs/rebuild_stats.log 2>&1 &
#   disown
# Then check progress any time with: tail -f logs/rebuild_stats.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOCK_FILE="/tmp/ltsbikeplan-rebuild-stats.lock"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another rebuild_stats_from_pmtiles.sh is already running (lock: $LOCK_FILE) - exiting." >&2
  exit 1
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Wraps every python invocation - idle I/O class, lowest CPU scheduling
# priority. No memory cap here deliberately: `ulimit -v` limits virtual
# address space, not actual RAM used, and pandas/numpy routinely reserve
# several GB of virtual space (observed ~3.8GB VSZ for well under 512MB
# of real RSS in testing) - a tight -v cap would abort these scripts on
# startup, not protect anything. If a hard memory ceiling is wanted on
# this 8GB box, use the systemd-run cgroup wrapper in the header comment
# above instead (MemoryMax=, a real RSS-aware limit).
run_low_priority() {
  ionice -c3 nice -n 19 "$@"
}

log "Repo root: $REPO_ROOT"

# --- Dependencies -----------------------------------------------------
# pmtiles/mapbox-vector-tile are only needed for the pmtiles-reconstruction
# fallback path (services/pmtiles_edges_service.py) - installed here only
# if missing, so a rerun doesn't hit the network for no reason. Uses
# --break-system-packages since this is a dedicated project server, not a
# shared multi-app box where that flag would be risky - drop it (or swap
# to a venv) if that doesn't hold on your setup.
if ! python3 -c "import pmtiles, mapbox_vector_tile" >/dev/null 2>&1; then
  log "Installing missing Python dependencies (pmtiles, mapbox-vector-tile)..."
  pip install --break-system-packages pmtiles mapbox-vector-tile
fi

DATA_DIR="${1:-${LTSBP_DATA_DIR:-$REPO_ROOT/data}}"
log "Using data_dir: $DATA_DIR"

log "Step 1/5: rebuilding web/data/italia_comuni_stats.json..."
run_low_priority python3 scripts/build_comuni_stats.py "$DATA_DIR"

log "Step 2/5: rebuilding web/data/italia_{provincia,regione}_stats.json..."
run_low_priority python3 scripts/build_regional_stats.py "$DATA_DIR"

log "Step 3/5: rebuilding web/data/interventions/*.json..."
run_low_priority python3 scripts/build_comuni_interventions.py "$DATA_DIR"

# Reads italia_comuni_stats.json (step 1's output) rather than pmtiles
# directly - no per-comune reconstruction here, just k-means over numbers
# already in that file, so this step is fast regardless of data_dir/pmtiles
# state. No data_dir argument: paths are fixed relative to the repo root
# (web/data/italia_comuni_stats.json in, web/data/italia_comuni_clusters.json
# out) - see the script's own module docstring.
log "Step 4/5: rebuilding web/data/italia_comuni_clusters.json..."
run_low_priority python3 scripts/build_comuni_clusters.py

# Same "reads step 1's output, no pmtiles/data_dir involved" reasoning as
# step 4 - the stats page's own "Scarica il dataset completo" button
# (web/stats/index.html) downloads this zip directly.
log "Step 5/5: rebuilding web/data/italia_comuni_stats.csv.zip..."
run_low_priority python3 scripts/build_comuni_stats_csv.py

log "Done."
python3 - <<'PY'
import json
comuni = json.load(open("web/data/italia_comuni_stats.json"))
regioni = json.load(open("web/data/italia_regione_stats.json"))
print(f"  {len(comuni)} comuni, {len(regioni)} regioni in italia_comuni_stats.json")
PY
import_count=$(ls web/data/interventions/*.json 2>/dev/null | wc -l)
log "  $import_count intervention file(s) in web/data/interventions/"
