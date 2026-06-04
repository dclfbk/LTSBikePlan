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
- LTS classification engine for edges and nodes with explicit decision-rule mapping.
- DEM-based slope integration with selectable slope strategies.
- Core map generation (`slope_map`, `lts_map`, `choropleth_lts_map`).
- Extended analysis modules for ESDA, clusters, network, gap, destination-access, accidents, and sum-up.
- Report generation (`report.md` + `report.html`) including only available artifacts.
- Manual-input diagnostics via `ltsbikeplan doctor`.

## Tech Stack

| Area | Tech |
|---|---|
| Language | Python 3.9+ |
| Packaging | `pyproject.toml` + setuptools |
| Core libs | `numpy`, `pandas`, `requests` |
| Geo/network | `geopandas`, `osmnx`, `shapely`, `networkx`, `folium`, `rasterio` |
| ML/analysis | `scikit-learn`, `matplotlib` |
| Optional | `rpy2`, `richdem` |
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

For geospatial/full pipeline modules:
```bash
pip install -r requirements-geo.lock.txt
pip install -e .[geo]
```

### Environment Variables
- `LTSBP_DEM_PATH` - Path to DEM `.tif` file used by `fetch`.
  - Default: `data/w51075_s10.tif`
- `LTSBP_SLOPE_STRATEGY` - Slope strategy selector (`v1`, `v2`, `v3`).
  - Default: `v3`
- `LTSBP_DATA_DIR` - Runtime data directory.
  - Default: `data/`
- `LTSBP_IMAGES_DIR` - Runtime output images directory.
  - Default: `images/`

### DEM Download (Manual)
LTSBikePlan requires a DEM `.tif` file for slope computation.

1. Open: `https://tinitaly.pi.ingv.it/Download_Area1_1.html`
2. Select the tile/quadrant(s) covering your study area.
3. Download the `.tif` file(s).
4. Provide the DEM to LTSBikePlan by either:
   - setting `LTSBP_DEM_PATH=/absolute/path/to/your_dem.tif`, or
   - placing a default file at `data/w51075_s10.tif`.

If your area spans multiple tiles, merge them first into a single `.tif`.

## Usage & Commands

Check setup and manual inputs:
```bash
ltsbikeplan doctor --city "Trento, Italy"
```

Run modular pipeline:
```bash
ltsbikeplan fetch --city "Trento, Italy"
ltsbikeplan compute-lts
ltsbikeplan maps --city "Trento, Italy"
ltsbikeplan report --city "Trento, Italy"
```

Run core end-to-end:
```bash
ltsbikeplan run --city "Trento, Italy" --with-report
```

Run full pipeline (includes extended analysis modules):
```bash
ltsbikeplan run-full --city "Trento, Italy" --with-report
```

Run tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Manual Inputs

Required:
- DEM raster (`LTSBP_DEM_PATH` or default `data/w51075_s10.tif`).

Optional (for extended sections):
- Accidents file: `data/accidents_<city>.geojson`.
- Population/destination datasets (used by destination-access/sum-up modules).

## Project Structure
```text
LTSBikePlan/
├── code/
│   ├── cli.py                        # thin CLI entry wrapper
│   ├── ltsbikeplan/
│   │   ├── assets/                   # static assets (rule dict, report css)
│   │   ├── domain/                   # core LTS domain logic
│   │   ├── services/                 # reusable services (graph, slope, report...)
│   │   ├── pipeline/                 # runtime pipelines and section modules
│   │   ├── cli.py                    # official CLI implementation
│   │   └── runtime_requirements.py   # manual input registry
│   └── old_code/                     # archived notebooks/legacy scripts
├── tests/                            # unit and smoke tests
├── .github/workflows/ci.yml          # CI pipeline
├── pyproject.toml                    # package metadata + entrypoints
├── requirements.lock.txt             # pinned core dependencies
├── requirements-geo.lock.txt         # pinned geospatial dependencies
└── README.md
```

## Contributing
1. Create a feature branch.
2. Keep changes modular under `code/ltsbikeplan/`.
3. Run tests locally before opening PR:
   - `python -m unittest discover -s tests -p "test_*.py"`

## License
This project is licensed under the **WTFPL v2**. See `LICENSE`.
