#!/usr/bin/env bash
# One-time provisioning for an Ubuntu box that will both serve web/ (via
# nginx - see deploy/nginx-stressinbici.conf) and run the periodic
# full-Italy rebuild (scripts/build_italy_map_cron.sh, via
# deploy/ltsbikeplan-rebuild.{service,timer}). Safe to re-run: apt/pip
# installs are idempotent, and cloning is skipped if DEPLOY_ROOT already
# has a checkout.
#
# tippecanoe and go-pmtiles aren't packaged in Ubuntu's apt repos, so both
# are built/installed from their upstream source - matches what's on the
# dev machine this pipeline was built against (tippecanoe v1.36.0).
# osmium-tool (apt) IS packaged, unlike those two - it backs
# services/osm_pbf_service.py::compute_bbox_from_pbf, which shells out to
# `osmium fileinfo` rather than depending on a Python OSM library for that
# one lookup.
#
# Usage: sudo scripts/setup_server.sh [deploy_root]
# Example: sudo scripts/setup_server.sh /opt/stressinbici
set -euo pipefail

DEPLOY_ROOT="${1:-/opt/stressinbici}"
REPO_URL="${LTSBP_REPO_URL:-https://github.com/dclfbk/LTSBikePlan.git}"
REPO_DIR="$DEPLOY_ROOT/LTSBikePlan"
TIPPECANOE_REF="${TIPPECANOE_REF:-1.36.0}"
PMTILES_VERSION="${PMTILES_VERSION:-1.24.0}" # go-pmtiles release tag (without the leading "v")

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo) - installs apt packages and writes to $DEPLOY_ROOT." >&2
  exit 1
fi

log "Installing apt dependencies..."
apt-get update -qq
apt-get install -y --no-install-recommends \
  git curl unzip build-essential \
  python3 python3-venv python3-pip \
  libsqlite3-dev zlib1g-dev \
  osmium-tool

log "Building tippecanoe v${TIPPECANOE_REF}..."
if ! command -v tippecanoe >/dev/null || [ "$(tippecanoe --version 2>&1 | grep -o '[0-9.]*$')" != "$TIPPECANOE_REF" ]; then
  TMP_TC="$(mktemp -d)"
  git clone --depth 1 --branch "$TIPPECANOE_REF" https://github.com/felt/tippecanoe.git "$TMP_TC"
  make -C "$TMP_TC" -j"$(nproc)"
  make -C "$TMP_TC" install
  rm -rf "$TMP_TC"
else
  log "tippecanoe v${TIPPECANOE_REF} already installed, skipping."
fi

log "Installing go-pmtiles v${PMTILES_VERSION}..."
if ! command -v pmtiles >/dev/null; then
  ARCH="$(dpkg --print-architecture)" # amd64 / arm64
  TMP_PM="$(mktemp -d)"
  curl -fsSL -o "$TMP_PM/pmtiles.tar.gz" \
    "https://github.com/protomaps/go-pmtiles/releases/download/v${PMTILES_VERSION}/go-pmtiles_${PMTILES_VERSION}_linux_${ARCH}.tar.gz"
  tar -xzf "$TMP_PM/pmtiles.tar.gz" -C "$TMP_PM" pmtiles
  install -m 755 "$TMP_PM/pmtiles" /usr/local/bin/pmtiles
  rm -rf "$TMP_PM"
else
  log "pmtiles already installed, skipping."
fi

log "Cloning/updating $REPO_URL into $REPO_DIR..."
mkdir -p "$DEPLOY_ROOT"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

log "Creating venv and installing ltsbikeplan (core + geo extras)..."
cd "$REPO_DIR"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.lock.txt -r requirements-geo.lock.txt -q
# Deliberately NOT `pip install -e ".[geo]"`: that resolves pyproject.toml's
# geo extras fresh, independent of the pins above, and pulls in richdem -
# which fails to build from source against modern CPython and separately
# forces a numpy<2 downgrade (see the comment in requirements-geo.lock.txt).
# Everything actually needed is already satisfied by the lock files above;
# this just registers the ltsbikeplan package/entry point.
pip install -e . -q
deactivate

log "Done. Next steps:"
log "  1. Install the nginx site: see deploy/nginx-stressinbici.conf"
log "  2. Install the rebuild timer: see deploy/ltsbikeplan-rebuild.{service,timer}"
log "  3. Run scripts/build_tiles.sh once for at least one area (or the full"
log "     rebuild service) so web/data/ isn't empty before nginx serves it."
