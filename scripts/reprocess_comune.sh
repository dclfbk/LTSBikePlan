#!/usr/bin/env bash
# Forces a full re-run of ONE comune outside the normal incremental cron
# (scripts/build_italy_map_comuni_cron.sh) - same per-comune steps as that
# script's own process_comune(), just callable by hand for a single istat
# instead of "whatever's next in comuni_progress.tsv". Needed because a
# comune already marked done there is otherwise never touched again, even
# after a pipeline fix or a manually-copied data file makes its old output
# stale (see the has_routing/comuni_index.json gap this was written for:
# reported live 2026-08-28, Palermo's routing.bin was updated by hand but
# web/data/comuni_index.json - a GLOBAL file covering all ~7893 comuni,
# see scripts/build_comuni_index.py - was not, so the site kept ignoring
# the new routing coverage).
#
# Usage: scripts/reprocess_comune.sh <slug> <istat> [area_name] [data_dir]
#   slug      - data/<slug>/ dir name and *_lts.pmtiles/*_routing.bin prefix
#   istat     - resolves the comune unambiguously (see AreaResolver -
#               a handful of comuni share a name, e.g. two "Paterno")
#   area_name - --area value passed to cli.py fetch/compute-lts; defaults
#               to slug (only diverges from it for the istat-suffixed
#               duplicate-name slugs, e.g. slug "Paterno_076100" but
#               --area "Paterno")
#   data_dir  - defaults to ./data, same as the cron script
#
# Example (Palermo, istat 082053):
#   scripts/reprocess_comune.sh Palermo 082053
#
# Skips the two whole-Italy rebuild steps at the end (national tileset +
# comuni_index.json) when LTSBP_SKIP_NATIONAL_REBUILD=1 - set it while
# reprocessing several comuni back to back on a slow box, so each one
# isn't separately paying for a full national tippecanoe merge (the
# expensive part - it re-merges every comune ever processed, not just the
# ones you just touched); run both by hand once at the end instead:
#   scripts/build_national_tiles.sh && python3 scripts/build_comuni_index.py
# Note comuni_index.json alone (no tileset rebuild) is comparatively cheap
# - it only lists what's already on disk, see build_comuni_index.py - so
# if all you need is has_routing/bbox to catch up (no NEW comune, no
# street-level detail change), running just that one script by hand may
# be all you actually need instead of this one at all.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SLUG="${1:?usage: reprocess_comune.sh <slug> <istat> [area_name] [data_dir]}"
ISTAT="${2:?usage: reprocess_comune.sh <slug> <istat> [area_name] [data_dir]}"
AREA_NAME="${3:-$SLUG}"
DATA_DIR="${4:-${LTSBP_DATA_DIR:-$REPO_ROOT/data}}"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cd "$REPO_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true  # harmless if already active / using a system install

log "--- $AREA_NAME ($SLUG, istat=$ISTAT) ---"

PYTHONPATH=code python3 code/cli.py fetch --area "$AREA_NAME" --area-level comune --istat "$ISTAT" --osmit-estratti
PYTHONPATH=code python3 code/cli.py compute-lts --area "$AREA_NAME" --area-level comune --istat "$ISTAT" --osmit-estratti

if [ "${LTSBP_CLEANUP_CACHE:-1}" = "1" ]; then
  PYTHONPATH=code python3 scripts/cleanup_area_cache.py "$AREA_NAME" --area-level comune --istat "$ISTAT" "$DATA_DIR" \
    || log "WARNING: cache cleanup failed for $AREA_NAME (LTS data itself is unaffected)"
fi

scripts/build_tiles.sh "$SLUG" "$DATA_DIR"
PYTHONPATH=code python3 scripts/build_routing_graph.py "$SLUG" "$DATA_DIR"

log "$AREA_NAME done."

if [ "${LTSBP_SKIP_NATIONAL_REBUILD:-0}" = "1" ]; then
  log "LTSBP_SKIP_NATIONAL_REBUILD=1 - skipping national tileset/comuni_index.json rebuild. Remember to run once you're done reprocessing:"
  log "  scripts/build_national_tiles.sh && python3 scripts/build_comuni_index.py"
else
  log "Rebuilding merged national tileset..."
  scripts/build_national_tiles.sh "$DATA_DIR"
  log "Rebuilding comuni index (istat/slug/bbox/has_routing)..."
  python3 scripts/build_comuni_index.py "$DATA_DIR"
  log "Done - $AREA_NAME's new data is live."
fi
