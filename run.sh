cd ~/dev/LTSBikePlan
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.lock.txt
pip install -r requirements-geo.lock.txt
pip install -e ".[geo]"
ltsbikeplan fetch --area Lavis --area-level comune
ltsbikeplan compute-lts --area Lavis --area-level comune
./scripts/build_tiles.sh Lavis

