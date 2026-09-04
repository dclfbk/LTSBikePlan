# LTSBikePlan
**Level of Traffic Stress bike-network pipeline for city-scale planning.**

LTSBikePlan computes bike network stress from OpenStreetMap + terrain data, then generates maps and analysis outputs to support safer cycling infrastructure decisions.

## Citation
If you use this project, please cite:

Venturoso, L., Usmani, M., Nanni, R., & Napolitano, M. (2026).
*LTS-BikePlan: A Data-Driven Tool for Enhancing Cycling Infrastructure and Safety.*
Journal of Urban Technology, 1-42. https://doi.org/10.1080/10630732.2026.2639290

## Key Features
- Modular CLI pipeline (`fetch`, `compute-lts`, `maps`, `report`, `run`, `run-full`, `doctor`).
- Works anywhere via `--area`/`--city` (both resolved through osmnx/Nominatim/Overpass by default, matching the original paper's tool) - pass `--osmit-estratti` to resolve `--area` against [osmit-estratti](https://osmit-estratti.wmcloud.org)'s pre-built Italian region/province/comune index instead, faster for large areas but Italy-only.
- DEM is fetched automatically per area from [Mapterhorn](https://mapterhorn.com) (open terrain tiles, 10m over Italy) - no more manual TINITALY download unless you want a higher-resolution local override, regardless of which area-fetch source you use.
- LTS classification engine for edges and nodes with explicit decision-rule mapping (including `highway=steps`: not bikeable - LTS 0 - unless the way carries a bicycle ramp, `ramp=yes` or `ramp:bicycle=yes`, which makes it LTS 1; a stressful street running alongside its own separated cycleway for most of its length is downgraded rather than flagged as a gap; `highway=trunk`/`motorroad=yes` are excluded as not legally bikeable; ways tagged `sac_scale`/`mtb:scale` above a walking/easy threshold are excluded as mountain trails, not bikeable infrastructure; `access` values that mean "not open to the general public" - `private`, `permit`, `customers`, `delivery`, `agricultural`, `forestry`, `destination`, `military` - are excluded too, and so is `highway=service` (driveways, parking aisles, alleys), unless a more specific `bicycle=yes`/`designated`/`permissive`/`official` tag explicitly overrides it).
- DEM-based slope integration with selectable slope strategies. A segment's slope is the mean of whichever ~10m DEM cells its geometry crosses, which isn't reliable on a short segment - too few cells for that mean to mean anything (measured directly against a real batch of short (<40m) mis-scored edges: median 17.8m crossed a median of only 3.5 cells, with a per-edge cell-to-cell spread up to ~6°, i.e. genuine measurement noise, not a real grade). Standard error of that mean shrinks as σ/√n_cells; solving for n_cells against the observed σ (~1-3°) to keep the residual error under ~1° (half a slope-class band's width) needs roughly 4-36 cells, i.e. ~40-360m depending on how conservative you want to be - `domain/lts_rules.py::BikePathAnalysis.slope_penalty`'s `MIN_RELIABLE_SLOPE_LENGTH_M` (500m) clears even the conservative end with margin, and gates every slope class this way (not just the "5-8: medium" one - "8-10: hard" and steeper used to apply with no length floor at all).
- Core map generation (`slope_map`, `lts_map`, `choropleth_lts_map`) plus a CRS-aware GeoParquet/GeoJSON export ready for vector tiling.
- Extended analysis modules for ESDA, clusters, network, gap, destination-access, accidents, and sum-up.
- Report generation (`report.md` + `report.html`) including only available artifacts.
- Manual-input diagnostics via `ltsbikeplan doctor`.
- A static [MapLibre GL JS](https://maplibre.org) + [PMTiles](https://protomaps.com/docs/pmtiles) viewer (`web/`) with a 3D terrain toggle, a gap-analysis panel (low-stress network "islands" + candidate segments to close the gaps between them), client-side bike routing, and a URL that mirrors the full view state for sharing - see [WEB.md](WEB.md) (and [ROUTING.md](ROUTING.md) for the routing engine specifically).

## Tech Stack

| Area | Tech |
|---|---|
| Language | Python 3.9+ |
| Packaging | `pyproject.toml` + setuptools |
| Core libs | `numpy`, `pandas`, `requests` |
| Geo/network | `geopandas`, `osmnx`, `shapely`, `networkx`, `folium`, `rasterio` |
| ML/analysis | `scikit-learn`, `matplotlib` |
| Optional | `rpy2` (legacy "v1" slope strategy only) |
| Testing | `unittest` |
| CI | GitHub Actions |

Dependency definitions:
- `pyproject.toml`
- `requirements.lock.txt`
- `requirements-geo.lock.txt`

## Getting Started

### Prerequisites
- Python 3.9+
- `pip`
- (Optional, for HTML report) `pandoc` (system package, not a pip dependency)

### Installation
```bash
git clone <your-fork-or-repo-url>
cd LTSBikePlan

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.lock.txt
pip install -e .
```

Install directly from a GitHub release tag:
```bash
pip install "git+https://github.com/dclfbk/LTSBikePlan.git@v3.0.0"
```

After installing, use the CLI from any shell:
```bash
ltsbikeplan doctor --city "Trento, Italy"
ltsbikeplan run-full --city "Bolzano, Italy" --with-report
```

If you want to reuse the code from another Python project, import the package modules directly:
```python
from ltsbikeplan.cli import main
from ltsbikeplan.services.slope_service import SlopeService
```

For geospatial/full pipeline modules:
```bash
pip install -r requirements-geo.lock.txt
pip install -e .
```
`pip install -e .` here (not `.[geo]`) just to install this package itself without pip re-resolving the `geo` extra's version ranges against the exact pins already installed from the lock file above; `richdem` isn't part of that extra any more (see `requirements-geo.lock.txt`'s own comment: `services/slope_strategies.py`'s slope computation no longer uses it, or GDAL, at all - point-sampling the DEM directly needs nothing beyond `rasterio`).

### Environment Variables
- `LTSBP_DEM_PATH` - Path to a local DEM `.tif` file, used by `fetch` instead of the automatic Mapterhorn download (see below).
  - Default: unset (DEM is fetched automatically)
- `LTSBP_SLOPE_STRATEGY` - Slope strategy selector (`v1`, `v2`, `v3`).
  - Default: `v3`
- `LTSBP_DATA_DIR` - Runtime data directory.
  - Default: `data/`
- `LTSBP_IMAGES_DIR` - Runtime output images directory.
  - Default: `images/`

### DEM (Automatic)
By default `fetch` downloads elevation data automatically for whatever area you pass via `--area`/`--city`, from [Mapterhorn](https://mapterhorn.com) (open Terrarium-encoded terrain tiles, 10m resolution over Italy - no account, no manual download). It's fetched once per area and cached under `LTSBP_DATA_DIR/_cache/`.

If you need a specific higher-resolution source instead (e.g. the 2-2.5m TINITALY tiles available in Alto Adige/Aosta), download it manually from [tinitaly.pi.ingv.it](https://tinitaly.pi.ingv.it/Download_Area1_1.html), merge multi-tile areas into a single `.tif`, and set `LTSBP_DEM_PATH=/absolute/path/to/your_dem.tif` - this skips the automatic Mapterhorn fetch entirely.

## Usage & Commands

Every command takes an area selector: `--area NAME` or `--city NAME` (equivalent - `--city` is kept as an alias for readability when naming a single place). Both resolve via osmnx/Nominatim/Overpass by default - works for any place worldwide, no extra dependency, matching how the original paper's tool worked. Add `--osmit-estratti` to resolve `--area` against [osmit-estratti](https://osmit-estratti.wmcloud.org)'s pre-built Italian region/province/comune index instead - faster for large regioni/province, and the only way to disambiguate a name that matches at more than one admin level (`--area-level {comune,provincia,regione}`) or select precisely by ISTAT code (`--istat CODE`); both flags are ignored without `--osmit-estratti`.

Check setup and manual inputs:
```bash
ltsbikeplan doctor --city "Trento, Italy"
```

Run modular pipeline (default: osmnx/Overpass):
```bash
ltsbikeplan fetch --area "Trento, Italy"
ltsbikeplan compute-lts --area "Trento, Italy"
ltsbikeplan maps --area "Trento, Italy"
ltsbikeplan report --area "Trento, Italy"
```

Run core end-to-end:
```bash
ltsbikeplan run --area "Trento, Italy" --with-report
```

Run full pipeline (includes extended analysis modules):
```bash
ltsbikeplan run-full --area "Provincia di Trento, Italy" --with-report
```

Faster Italy-only workflow via osmit-estratti's pre-built extracts:
```bash
ltsbikeplan run --area Trento --area-level comune --osmit-estratti --with-report
ltsbikeplan run-full --area "Provincia di Trento" --osmit-estratti --with-report
```

Run tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Web Viewer & Deployment

This README covers the data pipeline only. The public site built on top of it (`web/`) - the MapLibre viewer, the stats drill-down pages, tileset building, and the production nginx/systemd deployment - has its own doc: **[WEB.md](WEB.md)**. The client-side bike-routing engine specifically is documented separately in **[ROUTING.md](ROUTING.md)**.

## Manual Inputs

Optional (for extended sections):
- Accidents file: `data/accidents_<area_slug>.geojson`.
- Population/destination datasets (used by destination-access/sum-up modules).

## Project Structure
```text
LTSBikePlan/
├── code/
│   ├── cli.py                        # thin CLI entry wrapper
│   ├── ltsbikeplan/
│   │   ├── assets/                   # static assets (rule dict, report css)
│   │   ├── domain/                   # core LTS domain logic + AreaSpec/CRS constants
│   │   ├── services/                 # reusable services (graph, slope, DEM, OSM ingestion, export, report...)
│   │   ├── pipeline/                 # runtime pipelines and section modules
│   │   ├── cli.py                    # official CLI implementation
│   │   └── runtime_requirements.py   # manual input registry
│   └── old_code/                     # archived notebooks/legacy scripts
├── scripts/build_tiles.sh            # GeoJSON -> PMTiles build for one area
├── scripts/build_national_tiles.sh   # merges every processed area into one PMTiles tileset (capped z4-11)
├── scripts/build_comuni_index.py     # web/data/comuni_index.json - istat/slug/bbox for the z12+ per-comune swap
├── scripts/build_italy_map_cron.sh   # unattended full-Italy rebuild (all province)
├── scripts/build_italy_map_comuni_cron.sh  # same, at comune granularity, incremental/resumable
├── scripts/setup_server.sh           # one-time Ubuntu provisioning for production deploy
├── deploy/                           # nginx site config + systemd timer for production
├── web/                               # static MapLibre GL JS + PMTiles viewer (see WEB.md)
├── tests/                            # unit and smoke tests
├── pyproject.toml                    # package metadata + entrypoints
├── requirements.lock.txt             # pinned core dependencies
├── requirements-geo.lock.txt         # pinned geospatial dependencies
├── README.md                         # this file - data pipeline
├── WEB.md                            # web viewer, stats site, tileset builds, deployment
└── ROUTING.md                        # client-side bike-routing engine
```

Note: there is currently no `.github/workflows/` CI configuration in this repository despite earlier docs referencing one - tests are run manually (`python -m unittest discover -s tests -p "test_*.py"`).

## Contributing
1. Create a feature branch.
2. Keep changes modular under `code/ltsbikeplan/`.
3. Run tests locally before opening PR:
   - `python -m unittest discover -s tests -p "test_*.py"`

## License
This project is licensed under the **WTFPL v2**. See `LICENSE`.
