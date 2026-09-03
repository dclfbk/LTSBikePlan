# Vendored third-party scripts

Pinned exact-version browser builds, committed to the repo and served
locally instead of from a CDN's floating `@major` tag (e.g. `unpkg.com/
maplibre-gl@5`) - a floating tag resolves to whatever the latest matching
release is *at request time*, so the app could silently start running a
different minor/patch than what was actually tested, and a CDN outage
takes the whole site down with it.

| file | package | pinned to | why this exact version |
|---|---|---|---|
| `maplibre-gl-5.24.0.js` / `.css` | maplibre-gl | 5.24.0 | latest **5.x**; 6.x dropped the classic UMD/global `dist/maplibre-gl.js` build entirely (ESM-only `.mjs`), which this app can't use - no bundler, no `type="module"`, plain global-scope scripts throughout (see routing.js's own comment) |
| `pmtiles-4.5.0.js` | pmtiles | 4.5.0 | latest |
| `turf-7.4.0.min.js` | @turf/turf | 7.4.0 | latest; still ships a root `turf.min.js` UMD bundle |
| `jspdf-4.2.1.umd.min.js` | jspdf | 4.2.1 | latest; `dist/jspdf.umd.min.js` |
| `ngraph.graph-20.1.2.umd.js` | ngraph.graph | 20.1.2 | latest; global `createGraph` |
| `ngraph.path-1.6.1.umd.js` | ngraph.path | 1.6.1 | latest; global `ngraphPath` |
| `echarts-6.1.0.min.js` | echarts | 6.1.0 | latest; full `dist/echarts.min.js` (not `.simple.min.js` - the stats page uses boxplot and treemap series, which the simple build strips) |

maplibre-gl and pmtiles are loaded unconditionally (`<script defer>` in
index.html) since the map itself needs them on every visit. Turf, jsPDF
and ngraph.graph/ngraph.path are loaded on demand instead, via
`ensureTurfLoaded()` / `ensureJspdfLoaded()` / `ensureNgraphLoaded()` in
app.js - each is only needed by one specific feature (gap-buffer/
elevation geometry, PDF export, the router). echarts is loaded
unconditionally by web/stats/index.html only - that page is the only
thing that needs it.

## Bumping a version

1. Check the new version still ships a global/UMD browser build (not
   ESM-only) - `curl -s "https://unpkg.com/<pkg>@<version>/?meta"` and
   look for a `dist/*.umd*.js` or root `*.min.js` file.
2. Download it: `curl -sfL "https://unpkg.com/<pkg>@<version>/<path>" -o
   web/assets/vendor/<pkg>-<version>.js`
3. Rename the file to include the new version, update the `<script src>`
   (index.html) or `loadScriptOnce(...)` call (app.js) to match, and
   delete the old file.
4. Test the feature that library backs before deploying (map rendering
   for maplibre-gl/pmtiles; PDF export for jsPDF; elevation profile and
   the gap-selection buffer for turf; routing for ngraph).
