#!/usr/bin/env bash
# Uploads locally-computed web/data/ (the generated pmtiles/routing.bin/
# stats output - NOT web/'s code, see below) to the production server via
# rsync over SSH, for the "compute on a well-resourced laptop, deploy to
# the disk-constrained server" workflow: this repo's actual full-Italy
# web/data/ is ~28-30GB (24GB pmtiles + 3.6GB routing.bin, measured
# 2026-09-11) - the whole reason scripts/reprocess_italia_low_resource.sh
# exists is that a small VPS (4 CPU/8GB RAM/8GB disk) can't hold that much
# AND do the computation in the same place at the same time.
#
# rsync only transfers files that changed (by size+mtime, or --checksum
# for a slower byte-for-byte compare) - the first run moves everything,
# every run after that only moves whatever comuni you've reprocessed
# since, which is the whole point of doing this repeatedly rather than as
# a one-off copy.
#
# Deliberately scoped to web/data/ only, not the whole repo - code
# deployment (app.js/index.html/etc, see deploy/ and scripts/setup_server.sh)
# stays on its own path (git pull on the server, or however you already do
# it) so this never accidentally overwrites server-side code with whatever
# happens to be checked out on the laptop right now.
#
# Usage:
#   LTSBP_REMOTE_HOST=user@your-server scripts/sync_web_data_to_server.sh
# Optional:
#   LTSBP_REMOTE_PATH (default /var/www/stressinbici.it/data - see deploy/
#     nginx-stressinbici.conf's own `root`, NOT setup_server.sh's
#     DEPLOY_ROOT default; they're different paths in the real production
#     setup, see that nginx conf's own header comment)
#   LTSBP_SSH_PORT (default 22)
#   LTSBP_RSYNC_EXTRA_ARGS - appended verbatim to the rsync command, e.g.
#     LTSBP_RSYNC_EXTRA_ARGS="--dry-run" to preview what would transfer
#     without actually sending anything, or "--bwlimit=5000" to cap
#     upload speed (KB/s) so this doesn't saturate the connection while
#     someone's actually browsing the live site.
#
# --delete is NOT used - a comune that only exists locally so far (still
# mid-recompute) never gets removed from the server just because it
# hasn't reached web/data/ here yet in some OTHER sense; the server only
# ever gains files through this script, never loses them. If you
# genuinely need to remove a comune's files from the server (renamed
# istat/slug, real deletion), do that by hand.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${LTSBP_REMOTE_HOST:?set LTSBP_REMOTE_HOST=user@your-server}"
REMOTE_PATH="${LTSBP_REMOTE_PATH:-/var/www/stressinbici.it/data}"
SSH_PORT="${LTSBP_SSH_PORT:-22}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Syncing $REPO_ROOT/web/data/ -> $REMOTE_HOST:$REMOTE_PATH/ ..."
# shellcheck disable=SC2086
rsync -avz --progress \
  -e "ssh -p $SSH_PORT" \
  "$REPO_ROOT/web/data/" \
  "$REMOTE_HOST:$REMOTE_PATH/" \
  ${LTSBP_RSYNC_EXTRA_ARGS:-}

log "Done."
