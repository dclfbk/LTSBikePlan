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
- LTS classification engine for edges and nodes with explicit decision-rule mapping (including `highway=steps`: not bikeable - LTS 0 - unless the way carries a bicycle ramp, `ramp=yes` or `ramp:bicycle=yes`, which makes it LTS 1; a stressful street running alongside its own separated cycleway for most of its length is downgraded rather than flagged as a gap; `highway=trunk`/`motorroad=yes` are excluded as not legally bikeable; ways tagged `sac_scale`/`mtb:scale` above a walking/easy threshold are excluded as mountain trails, not bikeable infrastructure).
- DEM-based slope integration with selectable slope strategies.
- Core map generation (`slope_map`, `lts_map`, `choropleth_lts_map`) plus a CRS-aware GeoParquet/GeoJSON export ready for vector tiling.
- Extended analysis modules for ESDA, clusters, network, gap, destination-access, accidents, and sum-up.
- Report generation (`report.md` + `report.html`) including only available artifacts.
- Manual-input diagnostics via `ltsbikeplan doctor`.
- A static [MapLibre GL JS](https://maplibre.org) + [PMTiles](https://protomaps.com/docs/pmtiles) viewer (`web/`) with a 3D terrain toggle, a gap-analysis panel (low-stress network "islands" + candidate segments to close the gaps between them), and a URL that mirrors the full view state for sharing.

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

Install directly from a GitHub release tag:
```bash
pip install "git+https://github.com/dclfbk/LTSBikePlan.git@v2.2.4"
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
Deliberately `pip install -e .` here, not `pip install -e .[geo]`: the `geo` extra in `pyproject.toml` also lists `richdem` (the default "v3" slope strategy's preferred backend), which fails to *build* from source against modern CPython and separately forces a `numpy<2` downgrade that conflicts with the rest of this lock file - `pip install -e .[geo]` reliably fails on a clean install because of it. `requirements-geo.lock.txt` above already covers everything actually needed; `services/slope_service.py` falls back automatically (v3 → v2/GDAL → rasterio-simple) when richdem isn't importable, so skipping it doesn't lose functionality. Only install `richdem` by hand, into its own environment, if you specifically need that exact strategy.

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

## Web Viewer

Publicly, the viewer presents itself as **"Stress in bici"** (`web/i18n.js`'s `aboutHeading`) rather than the repo/package name - same underlying tool, product-facing branding for the live site. `web/index.html` is a static [MapLibre GL JS](https://maplibre.org) page (all JavaScript lives in `web/app.js`, not inline) that renders an area's LTS export as a clickable vector layer, with a switchable basemap (dark by default, or light/summer/cycling via the panel - all from [maptoolkit.org](https://styles.maptoolkit.org)) and, stacked as native map widgets under the zoom +/- control, fullscreen, a Nominatim place search restricted to Italy (magnifying-glass icon, expands to a search field), a 3D terrain toggle (🏔️, backed by [Mapterhorn](https://mapterhorn.com) - the same elevation source used for the slope calculation itself), and a PDF export button that renders the current map view, legend, title, comune name, map centre coordinates, and cartographic scale into a real downloadable PDF (via [jsPDF](https://github.com/parallax/jsPDF), not the browser print dialog). The LTS legend doubles as a filter: click a class to hide/show it. Comfort-framed, not stress-framed: LTS 1-4 read "molto tranquillo" → "molto impegnativo" (and equivalents in en/de/fr) with a matching face emoji (😌🙂😐😣) and a muted-teal-to-brick-red colour ramp (`#2A9D8F`/`#A8C957`/`#F4A261`/`#D1495B`) that also gets progressively thicker on the map - LTS 1-2 draw thin and light, LTS 3-4 thicker and bolder, so severity reads at a glance without needing the legend. Line rendering uses round joins/caps rather than MapLibre's default miter/butt, so winding rural/hillside roads trace a smooth curve at low zoom instead of a spiky zig-zag.

The language switcher at the top of the panel covers the whole UI (Italiano/English/Deutsch/Français) via `web/i18n.js` - one object per language with the same key set, including all 44 LTS decision-rule sentences keyed by `rule` code (mirroring `code/ltsbikeplan/assets/LTS_decisionrule_dict.json`'s `rule_message_dict`), so the "LTS rationale" in a popup is looked up in the current language rather than only showing the Italian sentence baked in at `compute-lts` time. Every rule sentence is plain description, not raw OSM syntax - "è un'autostrada," not `highway='motorway'`. Add a language by adding one more top-level key to `I18N` with the same shape.

Clicking a road (only above `MIN_CLICK_ZOOM` - zoom 14 by default, a single constant near the top of `web/index.html` if you want to retune it; streets are too close together to click reliably below that) shows its name, comune, LTS level (with the same emoji/colour as the legend), surface, and cycleway type. These read as plain sentences ("Strada asfaltata.", "Asphalt road.", "Straße mit Asphaltbelag.", "Route avec un revêtement en asphalte.") built from each language's `surface`/`cycleway`/`slope` phrase tables plus `surfaceTemplate`/`cyclewayTemplate` in `web/i18n.js` - a raw OSM value not in those dicts is simply omitted rather than shown verbatim, since tags like "sett" or "opposite_track" mean nothing to a non-mapper. If the street is flagged `is_gap_edge` (see below), the popup shows a 🔍 next to its name and, right under the LTS badge (not hidden in "Advanced details"), the same urgency + centrality explanation the priority list shows - so clicking any one street tells you on the spot whether/why it matters, not just its LTS number. Plus a collapsible "Advanced details" section with maxspeed/lanes/slope/length/rule.

The **"Tratti da valutare"** ("segments to evaluate" - not "priority interventions": not every flagged street necessarily has a feasible fix, especially at LTS 3) button opens a list of concrete streets to look at, scoped to what's currently on screen and gated by the same `MIN_CLICK_ZOOM` threshold as popup clicks (button disabled below it, with a "zoom in" hint if the panel is already open). It reads the high-stress segments that touch a *substantial* low-stress network (`is_gap_edge`, computed server-side by `domain/gap_analysis.py::annotate_gap_components` from low-stress *edges* directly, not from node LTS, so a boundary node isn't dropped by both sides - and downgraded back to `False` if the only island it touches is smaller than `MIN_GAP_ISLAND_LENGTH_KM` in `pipeline/compute_lts.py`, currently 1km, so a 2-edge residential loop in an isolated hamlet doesn't compete with a real urban gap) directly off the rendered map via `map.queryRenderedFeatures()` - no separate fetch, no Turf.js - aggregates them by street name (a real street is usually split into many OSM way segments) and ranks worst-first: highest LTS first, then highest betweenness centrality (`domain/network_centrality.py::annotate_edge_centrality`, sampled via networkx - how many shortest paths in the whole area are forced through that street, so "why does this matter" isn't just the LTS colour), then longest. Each row shows the street name/length/LTS plus a second line combining an LTS-based urgency word ("Intervento prioritario" for LTS 4, "Da valutare" for LTS 3) and a plain-language centrality phrase ("an almost mandatory passage to cross this area" down to "a minor link in the network", bucketed by quantile within the area's own distribution). Clicking a row highlights the street on the map and flies there (a real geographic buffer polygon around the selected street's own geometry, capped at zoom 21) and the list live-updates as you pan/zoom. This replaced an earlier "low-stress islands" design (graph-theory connected components) that turned out to be unreadable in practice - one Trento component alone listed 1374 undifferentiated edge fragments with no way to prioritize among them. The high-stress segments aren't drawn on the map on their own anymore (an unexplained purple overview wasn't earning its place) - they stay a real, queryable layer (`gap-edges`) at zero opacity, so the only purple a viewer sees is the highlight buffer around a segment actually picked from the list.

`web/` also ships the usual static-site SEO/sharing assets for `stressinbici.it`: `favicon.ico`, `robots.txt`, `sitemap.xml`, and `social-preview.png` (used by the Open Graph/Twitter meta tags in `index.html`'s `<head>`).

The URL mirrors the full view state (`area`, `zoom`, `lat`, `lon`, `pitch`, `bearing`, `bg`, `lts`, `terrain`, `gap`, `lang`) via `history.replaceState`, so a copied link reopens to the same camera position, basemap, active LTS filter, 3D terrain state, gap panel state, and language.

A site-level `<header>` sits above the map (title + current area, language switcher, and nav buttons) - separate from the map-level controls panel (legend, basemap, terrain, gap toggle) that floats over the map itself. The **"About"** nav button opens a panel with a short project blurb and the citation for the paper the tool is based on (Venturoso et al., 2026 - same reference as the Citation section above), with a link to the DOI. The **"FAQ"** nav button opens an accordion of common questions (what LTS means, what "Tratti da valutare" is and isn't, data sources, limitations). The **"Cookie"** nav button opens a placeholder panel - the site sets no cookies or tracking today, so there's nothing to consent to yet, but the panel is there to be filled in if that changes. All are same-page modals (`.info-panel` in `web/index.html`), not separate pages, wired through a small reusable `setupInfoPanel()` helper so another nav link reuses the same pattern.

1. Build a PMTiles tileset from one or more areas' `compute-lts` output (requires [`tippecanoe`](https://github.com/felt/tippecanoe) and [`pmtiles`](https://github.com/protomaps/go-pmtiles) on `PATH`):
   ```bash
   scripts/build_tiles.sh Trento              # single area -> web/data/Trento_lts.pmtiles (+ its gap_components.json)
   scripts/build_national_tiles.sh            # every area processed so far -> web/data/italia_lts.pmtiles (+ merged gap_components.json)
   ```
   Rerun `build_national_tiles.sh` any time after processing more areas to fold them into the merged tileset.

   For an unattended full-Italy rebuild (e.g. a weekly cron job on the machine serving `web/`), `scripts/build_italy_map_cron.sh` runs `fetch`+`compute-lts`+`build_tiles.sh` for every Italian provincia (`scripts/list_province.py` gets the ~107 names straight from osmit-estratti's own index, not a hardcoded list) and finishes with `build_national_tiles.sh` - one provincia failing is logged and skipped, not fatal to the run. Since it writes directly into `web/data/`, regenerating *is* publishing when the server already serves `web/` in place - no separate transfer step. `fetch`'s own downloads (each provincia's `.osm.pbf` extract + DEM mosaic) are cached under `data/_cache/` forever by default (no expiry - a full run leaves ~107 provincia-sized files on disk permanently); set `LTSBP_CLEANUP_CACHE=1` to delete each provincia's cache right after its `compute-lts` succeeds (`scripts/cleanup_area_cache.py`), trading disk space for re-downloading everything on the next run.
2. Serve `web/` with a static server that supports HTTP Range requests (PMTiles needs byte-range serving; Python's built-in `python -m http.server` does **not** support this - use `npx http-server web -c-1` or any CDN/object storage instead):
   ```bash
   npx http-server web -c-1
   ```
3. Open `http://localhost:8080/index.html?area=Trento` (single area) or `?area=italia` (merged tileset, also the default with no `?area=`) in a browser.

## Deployment (production, Ubuntu + nginx)

For a real deployment that also keeps itself up to date (rather than the local `npx http-server` dev setup above), `deploy/` and `scripts/setup_server.sh` provision an Ubuntu box that serves `web/` via nginx and rebuilds the national tileset on a weekly timer:

1. `sudo scripts/setup_server.sh [deploy_root]` (default `/opt/stressinbici`) - installs apt build dependencies, builds `tippecanoe` and installs `pmtiles` from their upstream releases (neither is in Ubuntu's apt repos), clones the repo, and creates the `.venv` with `requirements.lock.txt` + `requirements-geo.lock.txt` + `pip install -e .`. Safe to re-run for updates (`git pull` + reinstall).
2. `deploy/nginx-stressinbici.conf` - nginx site config for `web/`, with `.pmtiles` served ungzipped (gzip breaks the byte-range reads the PMTiles client relies on) and short, distinct cache lifetimes for tiles/data vs. HTML/JS so both a weekly data rebuild and a code deploy (`git pull`) become visible without a manual cache purge.
3. `deploy/ltsbikeplan-rebuild.service` + `deploy/ltsbikeplan-rebuild.timer` - a systemd timer running `scripts/build_italy_map_cron.sh` weekly (off-peak; a full run visits ~107 province and can take several hours). Each file's header comments have the exact install commands.

Code updates (new features/fixes) are a separate step from data rebuilds: `git -C /opt/stressinbici/LTSBikePlan pull && sudo systemctl restart nginx` picks up `web/` changes; re-run `scripts/setup_server.sh` if `pyproject.toml`/the lockfiles changed too.

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
├── scripts/build_national_tiles.sh   # merges every processed area into one PMTiles tileset
├── scripts/build_italy_map_cron.sh   # unattended full-Italy rebuild (all province)
├── scripts/setup_server.sh           # one-time Ubuntu provisioning for production deploy
├── deploy/                           # nginx site config + systemd timer for production
├── web/                               # static MapLibre GL JS + PMTiles viewer
├── tests/                            # unit and smoke tests
├── pyproject.toml                    # package metadata + entrypoints
├── requirements.lock.txt             # pinned core dependencies
├── requirements-geo.lock.txt         # pinned geospatial dependencies
└── README.md
```

Note: there is currently no `.github/workflows/` CI configuration in this repository despite earlier docs referencing one - tests are run manually (`python -m unittest discover -s tests -p "test_*.py"`).

## Contributing
1. Create a feature branch.
2. Keep changes modular under `code/ltsbikeplan/`.
3. Run tests locally before opening PR:
   - `python -m unittest discover -s tests -p "test_*.py"`

## License
This project is licensed under the **WTFPL v2**. See `LICENSE`.
