// Below this zoom, individual streets are too close together on screen to
// click reliably, and the point of a click is to inspect ONE street - a
// single named constant so the threshold is easy to retune later.
//
// Also drives belowGapZoom() (the "Tratti da valutare" list). Kept >=
// COMUNE_SWAP_MIN_ZOOM (12, defined further down) deliberately: as long as
// that holds, neither ever activates while the merged "italia" tileset's
// own lts-lines/gap-edges are the active layer (they stop rendering AT
// z12 - see COMUNE_SWAP_MIN_ZOOM) - only a per-comune source, which always
// carries the full property set, ever answers a click or feeds the gap
// list. That's what let build_national_tiles.sh strip italia_lts.pmtiles
// down to just the 3 properties actual rendering needs (lts/highway/
// rule) - name/length/centrality/is_gap_edge/etc. would otherwise still
// be needed there too. 13 (not 12 exactly) leaves one zoom level of
// margin rather than depending on the boundary being exact.
const MIN_CLICK_ZOOM = 13;

// Below this zoom, the lts-lines/gap-edges layers are hidden entirely (see
// MIN_STREETS_ZOOM on their `minzoom`, and #zoom-hint's show/hide further
// below) - skipping the layer entirely below this zoom means MapLibre
// doesn't fetch the "lts" source's tiles at those zooms either, not just
// hides them once fetched. Lowered to 4 (from 7) now that the tile build's
// own MAJOR_ROADS_FILTER (scripts/build_tiles.sh/build_national_tiles.sh)
// tiers by zoom instead of a single z<12 cutoff: motorway/trunk only at
// z4-5, +primary from z6, +secondary from z7 (unchanged), everything from
// z12 - so z4 is still a sparse, legible skeleton rather than the "solid
// mass of colour" every street segment at once would have been (the
// original reason this started at 8, back when every class rendered at
// every zoom).
const MIN_STREETS_ZOOM = 4;

// Area to load: web/index.html?area=<area_slug>, matching the file
// scripts/build_tiles.sh writes to web/data/<area_slug>_lts.pmtiles.
// "italia" (default) is the merged tileset from build_national_tiles.sh -
// it starts at a whole-Italy view rather than zooming to whatever areas
// happen to be computed so far (see the fitBounds guard below).
const params = new URLSearchParams(window.location.search);

// Compact, fully client-side, REVERSIBLE "share code" - not a true short
// link (this static site has no server/database to hold a mapping), just
// a denser encoding of the same state syncUrlState() below already puts
// in the address bar: short keys (already shortened, see that function)
// + only non-default values, base64url'd. ShareControl's "Condividi"
// button hands out a URL built from encodeShareState(); opening it
// decodes back to the same key/value pairs and layers them onto `params`
// right here (see the block below `area` unpacking further down for
// where that overlay happens), and the ordinary syncUrlState() call this
// script already makes on load rewrites the address bar into the normal,
// fully explicit "public" form - matching "ricodifica tutto per avere
// l'url pubblica": the ?c=... code is a transport detail, gone from the
// bar the moment the page has read it.
// Fixed field order, NOT a JSON object - this is what actually makes the
// code shorter than the equivalent query string. A JSON object repeats
// every key name ("area":"...", "z":"...", ...), which very nearly
// cancels out base64's own space savings; a plain "|"-joined positional
// list has none of that overhead (the schema is fixed/known, so position
// alone identifies each field - "|" is safe as a separator since none of
// these values can naturally contain one, `lts` already uses "," for its
// own internal list). The 4 routing fields are appended only when a route
// is active (see currentUrlState) - decodeShareState tells "no route" ​
// apart from "route present" by the split length alone.
const SHARE_FIELDS = ["area", "z", "y", "x", "p", "b", "bg", "lts", "t", "g", "lang"];
const SHARE_ROUTE_FIELDS = ["sy", "sx", "ey", "ex"];

function encodeShareState(stateObj) {
  const fields = SHARE_FIELDS.map((key) => stateObj[key] ?? "");
  if (stateObj.sy !== undefined) fields.push(...SHARE_ROUTE_FIELDS.map((key) => stateObj[key]));
  const raw = fields.join("|");
  const b64 = btoa(unescape(encodeURIComponent(raw))); // UTF-8 safe (area/lang names aren't ASCII-only)
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function decodeShareState(code) {
  let b64 = code.replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4) b64 += "=";
  const parts = decodeURIComponent(escape(atob(b64))).split("|");
  const result = {};
  SHARE_FIELDS.forEach((key, i) => { result[key] = parts[i]; });
  if (parts.length > SHARE_FIELDS.length) {
    SHARE_ROUTE_FIELDS.forEach((key, i) => { result[key] = parts[SHARE_FIELDS.length + i]; });
  }
  return result;
}
if (params.has("c")) {
  try {
    const decoded = decodeShareState(params.get("c"));
    for (const [key, value] of Object.entries(decoded)) params.set(key, String(value));
  } catch (error) {
    // Malformed/tampered code - fails open to whatever OTHER params (if
    // any) are present, same as any other missing-param case below.
  }
  params.delete("c");
}

const area = params.get("area") || "italia";
// "italia" (the merged whole-country tileset, and the default when no
// ?area= is given) is left unlabelled - stating it would just be noise
// on what's already the default view. Only a specific sub-area (e.g.
// ?area=Trento) is worth calling out next to the site name.
if (area !== "italia") {
  document.getElementById("area-badge").textContent = `(${area.replace(/_/g, " ")})`;
}

const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const pmtilesUrl = `pmtiles://${new URL(`data/${area}_lts.pmtiles`, window.location.href)}`;
const tiles = new pmtiles.PMTiles(pmtilesUrl.replace("pmtiles://", ""));
protocol.add(tiles);

// italia_lts.pmtiles (built by build_national_tiles.sh) is capped at
// maxzoom 11 - a whole-Italy tileset at full street-level detail measured
// 23.6GB, far past Cloudflare's free-plan 512MB per-file edge-cache
// ceiling. Past z11, this swaps in the relevant per-comune _lts.pmtiles
// (already built to z16 by build_tiles.sh) for whatever comuni are on
// screen, keyed by viewport-bbox overlap against web/data/comuni_index.json
// (see scripts/build_comuni_index.py) - so full detail is still available
// everywhere, just served from many small per-comune files instead of one
// giant merged one. Only meaningful for the merged "italia" view - a
// single-area page (?area=Trento) already IS the per-comune tileset, at
// full range, with nothing to swap to.
const COMUNE_SWAP_MIN_ZOOM = 12;
let comuniIndex = null;
let visibleComuneSlugs = new Set();
let comuniIndexPromise = null;

// Fetches web/data/comuni_index.json once, however it's first needed - by
// updateComuneOverlays' z12+ pmtiles swap (italia view only, see below) or
// by RoutingControl (any view - a route can need cross-comune coverage
// info regardless of which page loaded it). Concurrent/repeat callers
// share the same in-flight promise instead of re-fetching.
function ensureComuniIndexLoaded() {
  if (comuniIndex) return Promise.resolve(comuniIndex);
  if (!comuniIndexPromise) {
    comuniIndexPromise = fetch(new URL("data/comuni_index.json", window.location.href))
      .then((response) => response.json())
      .then((data) => {
        comuniIndex = data;
        return data;
      })
      // Missing/unreachable index just means no z12+ swap and no routing
      // coverage - callers already treat both as optional, so this fails
      // silent rather than throwing.
      .catch(() => {
        comuniIndexPromise = null;
        return null;
      });
  }
  return comuniIndexPromise;
}

function comuneSourceId(slug) { return `lts-${slug}`; }
function comuneLinesLayerId(slug) { return `lts-lines-${slug}`; }
function comuneGapLayerId(slug) { return `gap-edges-${slug}`; }
// Cosmetic-only twin of the national "lts-lines" layer, restricted to
// LTS 1/2 and drawn on top of it - see addDataLayers's own comment for
// why. Deliberately not part of ltsLineLayerIds()/hit-testing.
const LTS_PRIORITY_LAYER_ID = "lts-lines-priority";
// Street level - individual crossings (the whole reason this layer
// exists, see addDataLayers) are actually distinguishable on screen from
// here on. Below it, streets are too close together at this scale for
// which-one-is-on-top to read as anything but overall line density -
// not worth doubling the paint cost of a big city's full network for
// (reported: felt sluggish panning around Palermo, ~140k edges, two
// thirds of them lts 1/2 and therefore in this layer too).
const LTS_PRIORITY_MIN_ZOOM = 14;

// Every place that used to hard-code "lts-lines"/"gap-edges" now needs
// whichever of these is also currently active for the comuni in view -
// these two are the single source of truth for that, so filter/visibility/
// query-feature call sites stay in sync automatically as sources come and
// go on pan/zoom (see updateComuneOverlays below).
function ltsLineLayerIds() {
  if (!map.getLayer("lts-lines")) return [];
  return ["lts-lines", ...[...visibleComuneSlugs].map(comuneLinesLayerId)];
}
function gapEdgeLayerIds() {
  if (!map.getLayer("gap-edges")) return [];
  return ["gap-edges", ...[...visibleComuneSlugs].map(comuneGapLayerId)];
}

if (area === "italia") {
  ensureComuniIndexLoaded().then((data) => {
    if (data) updateComuneOverlays();
  });
}

const BASE_STYLES = {
  light: "https://styles.maptoolkit.org/light.json",
  summer: "https://styles.maptoolkit.org/summer.json",
  cycling: "https://styles.maptoolkit.org/cycling.json",
  dark: "https://styles.maptoolkit.org/dark.json",
};

// I18N comes from i18n.js. All UI text - legend labels, popup wording,
// gap panel, LTS decision-rule sentences (keyed by the `rule` code every
// edge already carries) - is looked up through it, so switching language
// never needs a different tileset or a Python re-run.
let currentLang = params.get("lang") in I18N ? params.get("lang") : "it";

function t(key) {
  return I18N[currentLang][key] ?? I18N.it[key];
}

function applyUiTranslations() {
  document.documentElement.lang = currentLang;
  document.getElementById("lang-select").value = currentLang;
  // Reuses aboutSubtitle rather than a separate key - same tagline,
  // shown both in the header (next to the site name) and at the top of
  // the About panel.
  document.getElementById("site-tagline").textContent = t("aboutSubtitle");
  document.getElementById("legend-hint").textContent = t("legendHint");
  document.getElementById("panel-toggle").textContent = t("legendToggle");
  document.getElementById("bg-light-label").textContent = t("bgLight");
  document.getElementById("bg-summer-label").textContent = t("bgSummer");
  document.getElementById("bg-cycling-label").textContent = t("bgCycling");
  document.getElementById("bg-dark-label").textContent = t("bgDark");
  document.getElementById("loading-title").textContent = t("loadingTitle");
  document.getElementById("zoom-hint").textContent = t("zoomHint");
  document.getElementById("terrain-toggle").title = t("terrainToggle");
  document.getElementById("print-toggle").title = t("printControl");
  document.getElementById("geocoder-input").placeholder = t("geocoderPlaceholder");
  document.getElementById("gap-toggle").textContent = t("gapToggle");
  document.getElementById("gap-heading").textContent = t("gapHeading");
  document.getElementById("gap-hint").textContent = t("gapHint");
  document.getElementById("about-toggle").textContent = t("aboutToggle");
  document.getElementById("about-heading").textContent = t("aboutHeading");
  document.getElementById("about-subtitle").textContent = t("aboutSubtitle");
  // aboutBody/faqItems[].a/footerCredit are the only innerHTML
  // assignments in this file - all authored, static content we control
  // in i18n.js (headings/bold/links), not user- or API-derived, so
  // there's nothing here to sanitize against.
  document.getElementById("about-body").innerHTML = t("aboutBody");
  document.getElementById("faq-toggle").textContent = t("faqToggle");
  document.getElementById("faq-heading").textContent = t("faqHeading");
  renderFaq();
  // Italian is the original About/FAQ text (see i18n.js); every other
  // language's version is an AI translation of it - disclosed here
  // rather than left implicit. Not shown for Italian itself, since
  // that's the source text, not a translation of anything.
  const aiNote = currentLang === "it" ? "" : t("aiTranslationNote") || "";
  document.getElementById("about-ai-note").textContent = aiNote;
  document.getElementById("about-ai-note").classList.toggle("hidden", !aiNote);
  document.getElementById("faq-ai-note").textContent = aiNote;
  document.getElementById("faq-ai-note").classList.toggle("hidden", !aiNote);
  document.getElementById("privacy-toggle").textContent = t("privacyToggle");
  document.getElementById("privacy-heading").textContent = t("privacyHeading");
  document.getElementById("privacy-intro").textContent = t("privacyIntro");
  document.getElementById("share-heading").textContent = t("shareModalHeading");
  document.getElementById("share-url-label").textContent = t("shareUrlLabel");
  document.getElementById("share-url-copy").textContent = t("shareCopyButton");
  document.getElementById("share-embed-label").textContent = t("shareEmbedLabel");
  document.getElementById("share-embed-copy").textContent = t("shareCopyButton");
  document.getElementById("share-social-label").textContent = t("shareSocialLabel");
  document.getElementById("footer-credit").innerHTML = t("footerCredit");
  document.getElementById("footer-hosting-text").textContent = t("footerHosting");
}

// Independent accordion items (opening one doesn't close another) -
// re-rendered on every applyUiTranslations() call, same as about-body,
// so a language switch shows that language's questions (currently
// Italian-only content, falls back via t()'s own I18N.it fallback).
function renderFaq() {
  const list = document.getElementById("faq-list");
  list.innerHTML = "";
  for (const item of t("faqItems") || []) {
    const wrapper = document.createElement("div");
    wrapper.className = "faq-item";
    const question = document.createElement("button");
    question.type = "button";
    question.className = "faq-question";
    question.textContent = item.q;
    const answer = document.createElement("div");
    answer.className = "faq-answer hidden";
    answer.innerHTML = item.a;

    // Small link at the bottom of the answer to collapse it again and
    // scroll back to the top of the panel - without it, a long FAQ
    // panel scrolled down to read one answer leaves the user stranded
    // mid-list with no easy way back to the question list.
    const closeLink = document.createElement("button");
    closeLink.type = "button";
    closeLink.className = "faq-close-answer";
    closeLink.textContent = t("faqCloseAndScrollUp");
    closeLink.addEventListener("click", () => {
      wrapper.classList.remove("open");
      answer.classList.add("hidden");
      document.getElementById("faq-panel").scrollTo({ top: 0, behavior: "smooth" });
    });
    answer.appendChild(closeLink);

    question.addEventListener("click", () => {
      const isOpen = wrapper.classList.toggle("open");
      answer.classList.toggle("hidden", !isOpen);
      // Centers the opened question in the panel's own scroll area
      // (#faq-panel has overflow-y:auto, not the page) - "block: center"
      // scrolls the nearest scrollable ancestor, so no manual math needed.
      if (isOpen) wrapper.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    wrapper.append(question, answer);
    list.appendChild(wrapper);
  }
}

// Every bit of view state the URL can restore: camera (zoom/lat/lon/pitch/
// bearing), basemap, which LTS classes the legend has active, and whether
// 3D terrain / the gap-analysis panel are on. Falls back to the
// whole-Italy default view when a param is missing (e.g. a fresh link).
// Short keys (z/y/x/p/b/t/g) are what syncUrlState() writes now - the
// long ones (zoom/lat/lon/pitch/bearing/terrain/gap) are read too, so a
// link shared/bookmarked before this shortening still opens correctly.
// Once opened, syncUrlState() rewrites the bar into the new short form
// anyway (replaceState, not pushState - no extra back-button entry).
function paramFloat(shortKey, longKey, fallback) {
  const raw = params.has(shortKey) ? params.get(shortKey) : params.has(longKey) ? params.get(longKey) : null;
  return raw === null ? fallback : parseFloat(raw);
}
function paramFlag(shortKey, longKey) {
  return params.get(shortKey) === "1" || params.get(longKey) === "1";
}
const hasExplicitView = params.has("z") || params.has("y") || params.has("x")
  || params.has("zoom") || params.has("lat") || params.has("lon");
const initialZoom = paramFloat("z", "zoom", 5.2);
const initialLat = paramFloat("y", "lat", 42.3);
const initialLon = paramFloat("x", "lon", 12.5);
const initialPitch = paramFloat("p", "pitch", 0);
const initialBearing = paramFloat("b", "bearing", 0);
let currentBasemap = params.get("bg") in BASE_STYLES ? params.get("bg") : "light";
let terrainOn = paramFlag("t", "terrain");
let gapModeOn = paramFlag("g", "gap");
document.getElementById("gap-panel").classList.toggle("open", gapModeOn);
document.getElementById("gap-toggle").classList.toggle("active", gapModeOn);

// #panel (legend/basemap/gap list) defaults to open on desktop, closed on
// phone-width viewports - a pure CSS default (see styles.css: the base
// rule vs. the @media (max-width: 480px) override), not a JS check here,
// so it stays correct across resize/orientation changes too, not just
// whatever the width was when this script ran. The click handler reads
// #panel-body's *current* computed visibility rather than assuming which
// default applies, and sets whichever override class (.collapsed or
// .expanded) actually flips it - same toggle works at any width.
document.getElementById("panel-toggle").addEventListener("click", () => {
  const panel = document.getElementById("panel");
  const isOpen = getComputedStyle(document.getElementById("panel-body")).display !== "none";
  panel.classList.toggle("collapsed", isOpen);
  panel.classList.toggle("expanded", !isOpen);
});

// 21 is the real ceiling for this map - the basemap styles top out there,
// so anything past it is just an empty/blank overzoom with no new detail.
// Set explicitly (not left to MapLibre's own default of 22) so every
// zoom-driving call - scroll/pinch, the +/- control, and any programmatic
// fitBounds/flyTo without its own maxZoom override - respects the same
// real limit.
const MAX_MAP_ZOOM = 21;

// Caps how far out the map can be zoomed/panned - roughly the Azores to
// the Urals, well past Italy's own extent so there's slack for exploring
// nearby countries, but tight enough to stop zooming out to a global (or
// blank-ocean) view. Deliberately NOT passed as the Map's own `maxBounds`
// option: that hard-clips every frame during a drag, which just feels
// like hitting a dead stop with no feedback. Instead left un-enforced
// during the gesture itself and corrected with an eased fitBounds once it
// ends (see clampToMaxBounds below) - the animation IS the "you can't go
// further" signal the user asked for.
const MAX_BOUNDS = new maplibregl.LngLatBounds(
  [-20.703401, 29.426147], // southwest
  [44.423552, 53.544187], // northeast
);

const map = window.map = new maplibregl.Map({
  container: "map",
  style: BASE_STYLES[currentBasemap],
  center: [initialLon, initialLat],
  zoom: initialZoom,
  pitch: initialPitch,
  bearing: initialBearing,
  maxZoom: MAX_MAP_ZOOM,
  // Required for PrintControl (below) to actually work: WebGL clears its
  // drawing buffer right after the browser compositor reads each frame
  // unless told to keep it, so without this canvas.toDataURL() - and a
  // browser's own print snapshot, for that matter - comes back blank. A
  // well-known Mapbox/MapLibre GL gotcha; MapLibre GL JS v5 nests this
  // under canvasContextAttributes rather than taking it as a top-level
  // Map option (confirmed by reading the actual bundle - the top-level
  // option is silently ignored, verified live: getContextAttributes()
  // still reported false with it set that way). Costs an extra GPU
  // buffer copy per frame; negligible next to everything else this map
  // already renders.
  canvasContextAttributes: { preserveDrawingBuffer: true },
});

// A MapLibre custom control stacks below whatever was added to the same
// position before it - adding this right after NavigationControl puts
// the 3D-terrain toggle directly under the zoom +/- buttons, as a native
// map widget instead of a floating text button in the side panel.
class TerrainControl {
  onAdd() {
    this._container = document.createElement("div");
    this._container.className = "maplibregl-ctrl maplibregl-ctrl-group";
    const button = document.createElement("button");
    button.id = "terrain-toggle";
    button.type = "button";
    button.textContent = "\u{1F3D4}\u{FE0F}"; // 🏔️ - terrain, matches the feature directly
    this._container.appendChild(button);
    return this._container;
  }
  onRemove() {
    this._container.remove();
  }
}

// Same stacking pattern as TerrainControl above - a print button as a
// native map widget. Prints via the browser's own print dialog (which
// every browser also offers as "Save as PDF"), not a custom PDF export -
// no new dependency, and print CSS further down hides everything that
// isn't the map/legend/scale so the output reads as "the map", not a
// screenshot of the whole page chrome.
function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  return [parseInt(clean.slice(0, 2), 16), parseInt(clean.slice(2, 4), 16), parseInt(clean.slice(4, 6), 16)];
}

// Ground resolution (metres per CSS pixel) of standard Web Mercator tiles
// at a given latitude/zoom - the same formula behind every slippy-map
// scale bar (Leaflet, Mapbox GL, etc). Used below to turn the on-screen
// map into a real cartographic scale ("1:25 000") once it's placed at a
// known physical size on the PDF page.
function metersPerPixel(lat, zoom) {
  return (156543.03392 * Math.cos((lat * Math.PI) / 180)) / Math.pow(2, zoom);
}

function formatCoord(value, positiveSuffix, negativeSuffix) {
  return `${Math.abs(value).toFixed(4)}°${value >= 0 ? positiveSuffix : negativeSuffix}`;
}

// Builds and downloads an actual PDF file (jsPDF, loaded in <head>) -
// not window.print(): a print dialog needs a manual "Save as PDF" step
// and, worse, doesn't reliably work at all for a WebGL map (see
// preserveDrawingBuffer on the Map constructor above - without it even
// the print path would capture a blank canvas). Composed from three
// pieces jsPDF draws independently: the map canvas as an image
// (map.getCanvas().toDataURL()), a legend drawn with jsPDF's own vector
// primitives (colour swatches from LTS_COLORS + i18n labels - not a
// screenshot of the on-page legend, so it stays crisp at any zoom the
// PDF viewer applies), and a title/attribution.
// Labels the PDF with an actual place name rather than the literal
// ?area= URL param, which is "italia" (the merged national tileset, see
// pipeline_output_inventory-style comments elsewhere) even while the user
// is looking at one specific comune within it. Looks up the map's current
// centre against comuni_index.json's bboxes (the same lookup
// updateComuneOverlays uses to decide which per-comune pmtiles to load) -
// NOT a queryRenderedFeatures() read of a "comune" tile property the way
// this used to work: italia_lts.pmtiles no longer carries that property at
// all (build_national_tiles.sh strips everything except lts/highway/rule,
// safe to do only because nothing interactive - clicks, the gap list, and
// now this - ever runs against it; see MIN_CLICK_ZOOM's comment). Gated on
// COMUNE_SWAP_MIN_ZOOM so a genuinely zoomed-out national/regional view
// still falls back to "Italia" instead of naming whichever comune the
// centre point happens to sit in; picks the smallest-bbox match when more
// than one comune's bbox contains the centre (a rough but cheap proxy for
// "most specific", same trade-off comuni_index.json's bbox-only lookup
// already accepts elsewhere).
function currentAreaLabel() {
  if (area !== "italia") return area.replace(/_/g, " ");
  if (!comuniIndex || map.getZoom() < COMUNE_SWAP_MIN_ZOOM) return "Italia";

  const center = map.getCenter();
  let best = null;
  let bestBboxArea = Infinity;
  for (const entry of comuniIndex) {
    const [minLon, minLat, maxLon, maxLat] = entry.bbox;
    if (center.lng < minLon || center.lng > maxLon || center.lat < minLat || center.lat > maxLat) continue;
    const bboxArea = (maxLon - minLon) * (maxLat - minLat);
    if (bboxArea < bestBboxArea) {
      bestBboxArea = bboxArea;
      best = entry;
    }
  }
  return best ? best.slug.replace(/_/g, " ") : "Italia";
}

function exportMapToPdf() {
  const canvas = map.getCanvas();
  const imgData = canvas.toDataURL("image/png");
  const orientation = canvas.width >= canvas.height ? "l" : "p";
  const doc = new jspdf.jsPDF({ orientation, unit: "mm", format: "a4" });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 10;
  const titleHeight = 12;
  const legendHeight = 10;
  const footerHeight = 12;

  doc.setFontSize(16);
  doc.setTextColor(30);
  doc.text(t("aboutHeading"), margin, margin + 6);
  doc.setFontSize(10);
  doc.setTextColor(100);
  const areaLabel = currentAreaLabel();
  doc.text(`${areaLabel} - ${new Date().toLocaleDateString(currentLang)}`, margin, margin + 11);

  const availableWidth = pageWidth - margin * 2;
  const availableHeight = pageHeight - margin * 2 - titleHeight - legendHeight - footerHeight;
  const imgAspect = canvas.width / canvas.height;
  let imgWidth = availableWidth;
  let imgHeight = imgWidth / imgAspect;
  if (imgHeight > availableHeight) {
    imgHeight = availableHeight;
    imgWidth = imgHeight * imgAspect;
  }
  const imgX = margin + (availableWidth - imgWidth) / 2;
  const imgY = margin + titleHeight;
  doc.addImage(imgData, "PNG", imgX, imgY, imgWidth, imgHeight);

  // Cartographic scale of the printed map: ground width covered by the
  // visible map (metersPerPixel * CSS-pixel width of the canvas, not its
  // devicePixelRatio-scaled backing-store width) divided by the physical
  // width the image ends up at on the page.
  const center = map.getCenter();
  const groundWidthMm = metersPerPixel(center.lat, map.getZoom()) * canvas.clientWidth * 1000;
  const scaleDenominator = Math.round(groundWidthMm / imgWidth);
  const centerText = `${t("pdfCenterLabel")}: ${formatCoord(center.lat, "N", "S")}, ${formatCoord(center.lng, "E", "O")}`;
  const scaleText = `${t("pdfScaleLabel")} 1:${scaleDenominator.toLocaleString(currentLang)}`;

  // Legend swatches: LTS_COLORS' numeric-string keys ("0".."4") always
  // enumerate in ascending order regardless of the object's own literal
  // key order (a JS spec quirk for integer-like keys) - same order the
  // on-page legend renders in, no explicit sort needed here either.
  let legendX = margin;
  const legendY = imgY + imgHeight + 6;
  doc.setFontSize(9);
  doc.setTextColor(0);
  for (const [key, color] of Object.entries(LTS_COLORS)) {
    const label = t("lts")[key] || key;
    const [r, g, b] = hexToRgb(color);
    doc.setFillColor(r, g, b);
    doc.rect(legendX, legendY, 4, 4, "F");
    doc.text(label, legendX + 6, legendY + 3.5);
    legendX += 6 + doc.getTextWidth(label) + 8;
  }

  doc.setFontSize(8);
  doc.setTextColor(130);
  doc.text(`${centerText}  ·  ${scaleText}`, margin, pageHeight - 10);
  doc.text("© OpenStreetMap contributors - stressinbici.it", margin, pageHeight - 5);

  const fileSlug = areaLabel.toLowerCase().replace(/\s+/g, "-");
  doc.save(`stress-in-bici-${fileSlug}.pdf`);
}

class PrintControl {
  onAdd() {
    this._container = document.createElement("div");
    this._container.className = "maplibregl-ctrl maplibregl-ctrl-group";
    const button = document.createElement("button");
    button.id = "print-toggle";
    button.type = "button";
    // A drawn PDF-file icon (document + folded corner + the classic Adobe-
    // red "PDF" band) rather than an emoji - no Unicode emoji actually
    // depicts a PDF specifically, and a generic document/printer glyph
    // doesn't say "this exports a PDF" as directly. Deliberately NOT tied
    // to the LTS palette (unlike an earlier version of this icon) - PDF-red
    // is its own universal convention, independent of stress-level colour.
    button.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 2 H14 L19 7 V22 H5 Z" fill="#f5f5f5" stroke="#888" stroke-width="1" stroke-linejoin="round" />
      <path d="M14 2 L19 7 H14 Z" fill="#cccccc" />
      <rect x="4" y="13" width="15" height="6" rx="1" fill="#E31B1C" />
      <text x="11.5" y="17.6" font-size="5.5" font-family="Arial, sans-serif" font-weight="bold" fill="white" text-anchor="middle">PDF</text>
    </svg>`;
    button.addEventListener("click", exportMapToPdf);
    this._container.appendChild(button);
    return this._container;
  }
  onRemove() {
    this._container.remove();
  }
}

// Builds the shareable link for the CURRENT view (camera/basemap/LTS
// filters/language, plus the active route if one is set - same state
// syncUrlState already keeps the address bar in sync with, via the
// shared currentUrlState() helper) - packed through encodeShareState()
// into one compact ?c=... code instead of the full query string, so
// what actually gets shared/pasted is short. See encodeShareState's own
// comment (top of file) for why decoding it back needs no server.
function shareUrl() {
  const url = new URL(window.location.href);
  url.search = "";
  url.searchParams.set("c", encodeShareState(currentUrlState()));
  return url.toString();
}

function buildEmbedCode(url) {
  return `<iframe src="${url}" width="600" height="450" style="border:0" loading="lazy" allowfullscreen></iframe>`;
}

// Plain URL-intent links - every one of these platforms accepts a share
// popup pre-filled from just a URL (+ text), no server round-trip or
// generated image needed: the shared card's preview picture comes from
// this site's own static Open Graph tags (index.html's og:image), the
// same for every link since this is a static site with no per-route
// server-rendered previews. Mastodon has no such single endpoint - it's
// federated, so which domain to open depends on which server the person
// posting actually has an account on (see the mastodon click handler in
// populateShareModal below).
const SOCIAL_SHARE_URL_BUILDERS = {
  facebook: (url) => `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
  linkedin: (url) => `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
  x: (url, text) => `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`,
  // wa.me is WhatsApp's own link-based share intent - opens the app on
  // mobile or WhatsApp Web on desktop with the message pre-filled, no
  // phone number needed since there's no fixed recipient.
  whatsapp: (url, text) => `https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`,
};

// Fills in the share modal's fields fresh on every open (setupInfoPanel's
// onOpen callback, see below) - the route/view can change between two
// opens of the same session, so this can't just be computed once.
function populateShareModal() {
  const url = shareUrl();
  const text = t("shareIntentText");
  document.getElementById("share-url-input").value = url;
  document.getElementById("share-embed-input").value = buildEmbedCode(url);
  document.getElementById("share-social-facebook").href = SOCIAL_SHARE_URL_BUILDERS.facebook(url);
  document.getElementById("share-social-linkedin").href = SOCIAL_SHARE_URL_BUILDERS.linkedin(url);
  document.getElementById("share-social-x").href = SOCIAL_SHARE_URL_BUILDERS.x(url, text);
  document.getElementById("share-social-whatsapp").href = SOCIAL_SHARE_URL_BUILDERS.whatsapp(url, text);
  // Mastodon has no single domain to post through - ask which server the
  // person actually has an account on, then use ITS OWN /share intent
  // (a route Mastodon's own web UI ships on every standard instance),
  // rather than depending on a third-party cross-instance redirector.
  document.getElementById("share-social-mastodon").onclick = () => {
    const instance = window.prompt(t("shareMastodonInstancePrompt"), "mastodon.social");
    if (!instance) return;
    const host = instance.trim().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    if (!host) return;
    window.open(`https://${host}/share?text=${encodeURIComponent(`${text} ${url}`)}`, "_blank", "noopener");
  };
}

// Copies one readonly field's value, with a visible fallback either way:
// the field is a real, selectable text input/textarea (not just a toast
// that vanishes in 3s), so even where the Clipboard API is blocked
// (permissions, insecure context, an older browser) the user can still
// select-and-copy by hand instead of the button doing nothing - this is
// what the previous copy-then-toast-only design was missing.
async function copyShareField(inputEl, buttonEl) {
  const originalLabel = buttonEl.textContent;
  try {
    await navigator.clipboard.writeText(inputEl.value);
    buttonEl.textContent = t("shareCopied");
    setTimeout(() => { buttonEl.textContent = originalLabel; }, 1500);
  } catch (error) {
    inputEl.focus();
    inputEl.select();
    if (inputEl.setSelectionRange) inputEl.setSelectionRange(0, inputEl.value.length);
  }
}
document.getElementById("share-url-copy").addEventListener("click", () => {
  copyShareField(document.getElementById("share-url-input"), document.getElementById("share-url-copy"));
});
document.getElementById("share-embed-copy").addEventListener("click", () => {
  copyShareField(document.getElementById("share-embed-input"), document.getElementById("share-embed-copy"));
});

class ShareControl {
  onAdd() {
    this._container = document.createElement("div");
    this._container.className = "maplibregl-ctrl maplibregl-ctrl-group";
    this._button = document.createElement("button");
    this._button.id = "share-toggle";
    this._button.type = "button";
    this._button.title = t("shareButton");
    this._button.textContent = "\u{1F517}"; // 🔗
    // Click handling lives in setupInfoPanel("share-toggle", "share-panel",
    // ...) further down, same as About/FAQ/Privacy - #share-panel is a
    // plain .info-panel modal, not something this control manages itself.
    this._container.appendChild(this._button);
    return this._container;
  }

  onRemove() {
    this._container.remove();
  }
}

// Nominatim geocoder, restricted to Italy (countrycodes=it) - a plain
// fetch against the public API, not a plugin: this project already
// avoids adding a dependency where a fetch call does the job (see
// parallel-cycleway/route-name fallback elsewhere in the codebase for
// the same reasoning). Debounced at 400ms to stay well under Nominatim's
// usage-policy limit of ~1 request/second for the public instance
// (https://operations.osmfoundation.org/policies/nominatim/).
//
// Collapsed to a magnifying-glass icon by default (same
// maplibregl-ctrl-group shape as TerrainControl/PrintControl) - a search
// box permanently sitting in the header nav read as part of the site's
// own navigation ("what does this search?") rather than "search the
// map", which misled users about what it does. Clicking the icon
// expands a flyout to the LEFT (not right - the control is pinned to
// the top-right corner, so a right-expanding panel would run off-screen).
class GeocoderControl {
  onAdd() {
    this._container = document.createElement("div");
    this._container.className = "maplibregl-ctrl maplibregl-ctrl-group geocoder-control";

    this._button = document.createElement("button");
    this._button.id = "geocoder-toggle";
    this._button.type = "button";
    this._button.textContent = "\u{1F50D}"; // 🔍
    this._button.addEventListener("click", () => this._toggle());
    this._container.appendChild(this._button);

    this._panel = document.createElement("div");
    this._panel.id = "geocoder-panel";
    this._panel.className = "hidden";
    this._panel.innerHTML = `
      <input type="text" id="geocoder-input" autocomplete="off" />
      <div id="geocoder-results" class="hidden"></div>
    `;
    this._container.appendChild(this._panel);

    this._input = this._panel.querySelector("#geocoder-input");
    this._results = this._panel.querySelector("#geocoder-results");
    this._debounce = null;
    this._requestId = 0;

    this._input.addEventListener("input", () => this._onInput());
    document.addEventListener("click", (e) => {
      if (!this._container.contains(e.target)) this._close();
    });

    return this._container;
  }

  onRemove() {
    this._container.remove();
  }

  _toggle() {
    const willOpen = this._panel.classList.contains("hidden");
    if (willOpen) this._open(); else this._close();
  }

  _open() {
    this._panel.classList.remove("hidden");
    this._button.classList.add("active");
    this._input.focus();
    // On a narrow phone screen there isn't room for both #panel (legend/
    // basemap/gap list) and this flyout without one covering the other -
    // see the mobile media query in styles.css. Hiding #panel while
    // actively searching is a reasonable trade: nobody is reading the
    // legend mid-search anyway.
    document.body.classList.add("geocoder-open");
  }

  _close() {
    this._panel.classList.add("hidden");
    this._button.classList.remove("active");
    this._hideResults();
    document.body.classList.remove("geocoder-open");
  }

  _hideResults() {
    this._results.classList.add("hidden");
    this._results.innerHTML = "";
  }

  _onInput() {
    clearTimeout(this._debounce);
    const query = this._input.value.trim();
    if (query.length < 3) {
      this._hideResults();
      return;
    }
    this._debounce = setTimeout(() => this._search(query), 400);
  }

  async _search(query) {
    const requestId = ++this._requestId;
    const url = new URL("https://nominatim.openstreetmap.org/search");
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("q", query);
    url.searchParams.set("countrycodes", "it");
    url.searchParams.set("limit", "6");
    url.searchParams.set("accept-language", currentLang);

    let results;
    try {
      const response = await fetch(url);
      results = await response.json();
    } catch (error) {
      return;
    }
    // A newer keystroke already fired another request while this one
    // was in flight - drop this stale response instead of racing it
    // into the dropdown out of order.
    if (requestId !== this._requestId) return;

    this._results.innerHTML = "";
    if (!results.length) {
      this._hideResults();
      return;
    }
    for (const result of results) {
      const item = document.createElement("div");
      item.className = "geocoder-item";
      item.textContent = result.display_name;
      item.addEventListener("click", () => {
        // Nominatim's boundingbox is [south, north, west, east] as
        // strings; fitBounds wants [[west, south], [east, north]] as numbers.
        const [south, north, west, east] = result.boundingbox.map(Number);
        map.fitBounds([[west, south], [east, north]], { padding: 60, maxZoom: MAX_MAP_ZOOM, duration: 800 });
        this._input.value = result.display_name;
        this._close();
      });
      this._results.appendChild(item);
    }
    this._results.classList.remove("hidden");
  }
}

// State shared between RoutingControl (the panel UI below) and the map's
// global "click" handler further down this file. There's no explicit
// "pick mode" toggle any more (see RoutingControl's own comment) - a plain
// map click while the panel is open fills whichever of start/end isn't
// set yet, in order; routingNextPickTarget() below is the single source
// of truth both the click handler and the cursor styling read from.
let routingPanelOpen = false;
let routingStart = null; // maplibregl.LngLat | null
let routingEnd = null;
let routingStartMarker = null;
let routingEndMarker = null;
let routingPartialEndMarker = null; // marks where a PARTIAL route (findRoute's `partial: true`) actually ends - distinct from routingEndMarker, which stays at the point the rider asked for
let routingHasEverRouted = false; // gates fitBounds to "first route only" - see _applyRoute
let routingControlInstance = null; // set by RoutingControl.onAdd, so the click handler can hand picked points back to the panel
const routingFileCache = new Map(); // slug -> decodeRoutingGraphBinary() result for <slug>_routing.bin (never caches a failed fetch, so a transient network error can be retried)
// sorted-slugs key -> mergeRoutingGraphs() result. Populating one ngraph.graph
// is the dominant cost once a comune's binary is already decoded (~550ms at
// Trento's node/edge count, measured - see routing perf notes), and
// _findRoute rebuilds it from scratch on every call: once per widen-retry
// margin within a single search, and again on every drag/reroute even when
// the candidate comuni haven't changed at all. Never evicted, same
// unbounded-but-small-in-practice convention as routingFileCache above.
const mergedGraphCache = new Map();

function routingNextPickTarget() {
  if (!routingPanelOpen) return null;
  if (!routingStart) return "start";
  if (!routingEnd) return "end";
  return null; // both set - further map clicks don't set points (drag the existing markers instead)
}

// Small teardrop pin, same silhouette family as maplibregl.Marker's own
// default icon - used as the cursor while picking a routing point, so the
// cursor previews the actual marker about to be dropped (colour matches
// setPoint's marker colours below) instead of a generic crosshair.
function pinSvg(color) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="32" viewBox="0 0 24 32"><path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20C24 5.4 18.6 0 12 0z" fill="${color}" stroke="white" stroke-width="1.5"/><circle cx="12" cy="12" r="4" fill="white"/></svg>`;
}
// Hotspot (12,30) points at the pin's tip, matching where the real marker
// anchors once dropped.
const START_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(pinSvg("#2E7D32"))}") 12 30, crosshair`;
const END_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(pinSvg("#C62828"))}") 12 30, crosshair`;

// Rough gradient-adjusted cycling speed model, for the estimated-time
// line in the route summary (RoutingControl._renderElevationProfile,
// which already samples {km, elev} points along the route for the
// altimetric chart - this reuses those, no extra data needed). Assumes a
// muscular (non-electric) bike: flat-ground baseline CYCLING_FLAT_KMH,
// slowed on climbs, sped up (capped) on descents, by the real gradient
// between consecutive sampled points. Deliberately simple/transparent
// over "accurate" - no wind, fitness level, stops or traffic lights - see
// this formula documented in plain language in the routing panel's own
// "Come funziona questo calcolo" disclaimer and in the FAQ (both must
// stay in sync with this if the constants change).
const CYCLING_FLAT_KMH = 18;
const CYCLING_MIN_KMH = 4;
const CYCLING_MAX_KMH = 40;
const CYCLING_CLIMB_KMH_PER_PERCENT = 1.5;
const CYCLING_DESCENT_KMH_PER_PERCENT = 1.2;

function estimateCyclingSpeedKmh(slopePercent) {
  if (slopePercent >= 0) {
    return Math.max(CYCLING_MIN_KMH, CYCLING_FLAT_KMH - slopePercent * CYCLING_CLIMB_KMH_PER_PERCENT);
  }
  return Math.min(CYCLING_MAX_KMH, CYCLING_FLAT_KMH + Math.abs(slopePercent) * CYCLING_DESCENT_KMH_PER_PERCENT);
}

// `points`: [{km, elev}, ...], the same array _renderElevationProfile
// builds for the chart. Returns total estimated minutes.
function estimateRouteTimeMinutes(points) {
  let totalHours = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const distKm = points[i + 1].km - points[i].km;
    if (distKm <= 0) continue;
    const riseM = points[i + 1].elev - points[i].elev;
    const slopePercent = (riseM / (distKm * 1000)) * 100;
    totalHours += distKm / estimateCyclingSpeedKmh(slopePercent);
  }
  return totalHours * 60;
}

// Merges CONSECUTIVE segments (one per original graph edge, from
// findRoute's `segments` return) sharing the same (name, lts,
// facilityCode, comuneSlug) into "runs" - the single shared data
// structure behind the coloured map layer, the click popup, the summary
// bars, and all three downloads. startKm/endKm are cumulative over the
// WHOLE route (not per-comune).
function buildRouteRuns(segments, coordinates) {
  const runs = [];
  let cumKm = 0;
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const last = runs[runs.length - 1];
    if (last && last.name === seg.name && last.lts === seg.lts
        && last.facilityCode === seg.facilityCode && last.comuneSlug === seg.comuneSlug) {
      last.coords.push(coordinates[i + 1]);
      last.lengthM += seg.lengthM;
    } else {
      runs.push({
        coords: [coordinates[i], coordinates[i + 1]],
        name: seg.name, lts: seg.lts, facilityCode: seg.facilityCode, comuneSlug: seg.comuneSlug,
        lengthM: seg.lengthM, startKm: cumKm,
      });
    }
    cumKm += seg.lengthM / 1000;
    runs[runs.length - 1].endKm = cumKm;
  }
  return runs;
}

function routeRunsToFeatureCollection(runs) {
  return {
    type: "FeatureCollection",
    features: runs.map((run) => ({
      type: "Feature",
      properties: { lts: run.lts, name: run.name, comuneSlug: run.comuneSlug, startKm: run.startKm, endKm: run.endKm },
      geometry: { type: "LineString", coordinates: run.coords },
    })),
  };
}

function _xmlEscape(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function downloadTextFile(filename, mimeType, content) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildRouteGeoJson(runs) {
  const fc = {
    type: "FeatureCollection",
    features: runs.map((r) => ({
      type: "Feature",
      properties: { name: r.name || null, lts: r.lts, lts_label: t("lts")[String(r.lts)] || null, length_m: Math.round(r.lengthM) },
      geometry: { type: "LineString", coordinates: r.coords },
    })),
  };
  return JSON.stringify(fc, null, 2);
}

function buildRouteGpx(runs) {
  const tracks = runs
    .map((r) => {
      const ltsLabel = t("lts")[String(r.lts)] || "";
      const name = _xmlEscape(`${r.name || t("popupNoName")} (${ltsLabel})`);
      const points = r.coords.map(([lon, lat]) => `      <trkpt lat="${lat}" lon="${lon}"></trkpt>`).join("\n");
      return `  <trk>\n    <name>${name}</name>\n    <trkseg>\n${points}\n    </trkseg>\n  </trk>`;
    })
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Stress in bici" xmlns="http://www.topografix.com/GPX/1/1">\n${tracks}\n</gpx>`;
}

function buildRouteKml(runs) {
  const placemarks = runs
    .map((r) => {
      const ltsLabel = t("lts")[String(r.lts)] || "";
      const name = _xmlEscape(r.name || t("popupNoName"));
      const coords = r.coords.map(([lon, lat]) => `${lon},${lat},0`).join(" ");
      return `  <Placemark>\n    <name>${name}</name>\n    <description>${_xmlEscape(ltsLabel)}</description>\n    <LineString><coordinates>${coords}</coordinates></LineString>\n  </Placemark>`;
    })
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n${placemarks}\n</Document>\n</kml>`;
}

// Client-side LTS-preferring bike routing (web/routing.js's
// candidateComuniForRoute/mergeRoutingGraphs/findRoute - no routing
// server). Same toggle-button + left-flyout-panel shape as
// GeocoderControl just above, stacked directly below it - but unlike
// GeocoderControl, this panel does NOT close on an outside click: the
// whole interaction (click map for start, click again for end) happens
// while it's open, so auto-closing on the very click that sets a point
// would force a re-open for the second one. It closes only via its own
// toggle button (see _open/_close - no document-level click listener).
class RoutingControl {
  onAdd() {
    routingControlInstance = this;
    this._container = document.createElement("div");
    this._container.className = "maplibregl-ctrl maplibregl-ctrl-group routing-control";

    this._button = document.createElement("button");
    this._button.id = "routing-toggle";
    this._button.type = "button";
    this._button.textContent = "\u{1F6B2}"; // 🚲
    this._button.addEventListener("click", () => this._toggle());
    this._container.appendChild(this._button);

    this._panel = document.createElement("div");
    this._panel.id = "routing-panel";
    this._panel.className = "hidden";
    this._panel.innerHTML = `
      <div class="routing-panel-header">
        <span class="routing-panel-title">${t("routingToggle")}</span>
        <span class="routing-panel-header-buttons">
          <button type="button" id="routing-panel-expand" class="routing-panel-close">&#9974;</button>
          <button type="button" id="routing-panel-close" class="routing-panel-close">&times;</button>
        </span>
      </div>
      <p class="routing-hint">${t("routingClickHint")}</p>
      <div class="routing-point-row" id="routing-start-row">
        <span class="routing-point-dot" style="background:#2E7D32"></span>
        <span class="routing-point-label">${t("routingStartLabel")}</span>
      </div>
      <div class="routing-point-row" id="routing-end-row">
        <span class="routing-point-dot" style="background:#C62828"></span>
        <span class="routing-point-label">${t("routingEndLabel")}</span>
      </div>
      <button type="button" id="routing-clear">${t("routingClearButton")}</button>
      <div id="routing-status" class="hidden">
        <span id="routing-status-spinner" class="spinner hidden"></span>
        <span id="routing-status-text"></span>
      </div>
      <details class="routing-disclaimer">
        <summary>${t("routingDisclaimerSummary")}</summary>
        <p>${t("routingDisclaimerBody")}</p>
      </details>
      <div id="routing-summary" class="hidden">
        <div id="routing-lts-bar" class="routing-stacked-bar"></div>
        <div id="routing-total-km" class="routing-total-km"></div>
        <div id="routing-estimated-time" class="routing-caption hidden"></div>
        <div id="routing-facility-bar" class="routing-stacked-bar"></div>
        <div id="routing-facility-legend" class="routing-facility-legend"></div>
        <div class="routing-caption">${t("routeElevationHeading")}</div>
        <div id="routing-elevation-chart" class="routing-elevation-chart"></div>
        <div class="routing-caption">${t("routeDownloadHeading")}</div>
        <div class="routing-download-buttons">
          <button type="button" id="routing-download-geojson">${t("routeDownloadGeoJson")}</button>
          <button type="button" id="routing-download-gpx">${t("routeDownloadGpx")}</button>
          <button type="button" id="routing-download-kml">${t("routeDownloadKml")}</button>
        </div>
      </div>
    `;
    this._container.appendChild(this._panel);

    // NOT inside this._panel/this._container - MapLibre's own
    // .maplibregl-ctrl CSS sets `transform: translate(0)` on every
    // control (including this one), which makes it the containing block
    // for any `position:fixed` DESCENDANT, trapping the tooltip inside
    // the panel's own box instead of positioning it against the real
    // viewport (confirmed via real browser testing: the tooltip's set
    // `left`/`top` matched what _moveBarTooltip computed, but its actual
    // getBoundingClientRect() was offset by hundreds of pixels). Appended
    // to <body> directly sidesteps that entirely.
    this._barTooltip = document.createElement("div");
    this._barTooltip.id = "routing-bar-tooltip";
    this._barTooltip.className = "routing-bar-tooltip hidden";
    document.body.appendChild(this._barTooltip);

    this._closeBtn = this._panel.querySelector("#routing-panel-close");
    this._expandBtn = this._panel.querySelector("#routing-panel-expand");
    this._startRow = this._panel.querySelector("#routing-start-row");
    this._endRow = this._panel.querySelector("#routing-end-row");
    this._clearBtn = this._panel.querySelector("#routing-clear");
    this._status = this._panel.querySelector("#routing-status");
    this._statusSpinner = this._panel.querySelector("#routing-status-spinner");
    this._statusText = this._panel.querySelector("#routing-status-text");
    this._summary = this._panel.querySelector("#routing-summary");
    this._ltsBar = this._panel.querySelector("#routing-lts-bar");
    this._totalKmEl = this._panel.querySelector("#routing-total-km");
    this._estimatedTimeEl = this._panel.querySelector("#routing-estimated-time");
    this._facilityBar = this._panel.querySelector("#routing-facility-bar");
    this._facilityLegend = this._panel.querySelector("#routing-facility-legend");
    this._elevationChart = this._panel.querySelector("#routing-elevation-chart");
    this._runs = []; // current route's runs (buildRouteRuns) - feeds the 3 download buttons

    this._clearBtn.addEventListener("click", () => this._clear());
    this._closeBtn.addEventListener("click", () => this._close());
    this._expandBtn.addEventListener("click", () => this._setExpanded(!this._panel.classList.contains("expanded")));
    window.addEventListener("resize", () => {
      if (this._panel.classList.contains("expanded")) this._positionExpandedPanel();
      else this._updateCompactPanelMaxHeight();
    });
    this._panel.querySelector("#routing-download-geojson").addEventListener("click", () => {
      downloadTextFile("percorso.geojson", "application/geo+json", buildRouteGeoJson(this._runs));
    });
    this._panel.querySelector("#routing-download-gpx").addEventListener("click", () => {
      downloadTextFile("percorso.gpx", "application/gpx+xml", buildRouteGpx(this._runs));
    });
    this._panel.querySelector("#routing-download-kml").addEventListener("click", () => {
      downloadTextFile("percorso.kml", "application/vnd.google-earth.kml+xml", buildRouteKml(this._runs));
    });
    // No document-level "click outside closes" listener - see the class
    // comment above for why this panel stays open until its own toggle.

    return this._container;
  }

  onRemove() {
    this._panel.remove(); // may be reparented to <body> right now (expanded mode) - remove it explicitly rather than assuming it's still inside this._container
    this._container.remove();
    this._barTooltip.remove(); // appended to <body>, not this._container - see onAdd's comment
    routingControlInstance = null;
  }

  _toggle() {
    const willOpen = this._panel.classList.contains("hidden");
    if (willOpen) this._open(); else this._close();
  }

  _open() {
    this._panel.classList.remove("hidden");
    this._button.classList.add("active");
    document.body.classList.add("routing-open");
    routingPanelOpen = true;
    this._updateCursor();
    this._updateCompactPanelMaxHeight();
  }

  // Real max-height for the compact (anchored-to-the-button) panel,
  // replacing the CSS calc(100vh - 90px) guess at #routing-panel's base
  // rule - that value assumes the panel starts right at the top of the
  // viewport, but it actually starts wherever MapLibre floats the control
  // (below the real site header + the library's own 10px margin), so on
  // any page with a header the CSS guess left the panel's bottom edge -
  // and the download buttons inside it - below the visible viewport with
  // nothing to scroll it into view (the panel's own overflow-y:auto only
  // rescues content taller than ITS box, not the box itself sitting
  // partly off-screen - this is exactly the bug already found and fixed
  // for the mobile flyout below via a vh-fraction; this does the same job
  // more precisely via a real measurement, and covers desktop too). A
  // no-op while expanded - that state is sized by top/bottom instead, see
  // _positionExpandedPanel.
  _updateCompactPanelMaxHeight() {
    if (this._panel.classList.contains("hidden") || this._panel.classList.contains("expanded")) return;
    const panelTop = this._panel.getBoundingClientRect().top;
    const footerTop = document.getElementById("site-footer").getBoundingClientRect().top;
    const margin = 12;
    this._panel.style.maxHeight = `${Math.max(150, footerTop - panelTop - margin)}px`;
  }

  _close() {
    // Collapse first if expanded - otherwise the panel stays reparented
    // to <body> (see _setExpanded) and the NEXT _open() would render it
    // there instead of back in its normal anchored corner slot.
    if (this._panel.classList.contains("expanded")) this._setExpanded(false);
    this._panel.classList.add("hidden");
    this._button.classList.remove("active");
    document.body.classList.remove("routing-open");
    routingPanelOpen = false;
    this._updateCursor();
  }

  _updateCursor() {
    const target = routingNextPickTarget();
    map.getCanvas().style.cursor = target === "start" ? START_CURSOR : target === "end" ? END_CURSOR : "";
  }

  // Expanded mode reparents the panel to <body> (see the CSS comment on
  // #routing-panel.expanded for why: escapes .maplibregl-ctrl's own
  // `transform: translate(0)`, which would otherwise trap a fixed-
  // position panel against the CONTROL's box instead of the real
  // viewport - the same bug already found/fixed for the bar tooltip).
  // Collapsing moves it straight back to its normal anchored slot inside
  // the control.
  _setExpanded(expanded) {
    this._panel.classList.toggle("expanded", expanded);
    this._expandBtn.classList.toggle("active", expanded);
    if (expanded) {
      document.body.appendChild(this._panel);
      this._positionExpandedPanel();
    } else {
      this._container.appendChild(this._panel);
      this._panel.style.top = "";
      this._panel.style.bottom = "";
    }
  }

  // Constrains the expanded panel between the REAL header/footer edges,
  // measured live rather than assumed - both can wrap to a second line
  // depending on language/viewport width, so a fixed CSS offset would be
  // wrong for some of them. Re-run on window resize (see onAdd) since a
  // resize can change whether they wrap.
  _positionExpandedPanel() {
    const headerBottom = document.getElementById("site-header").getBoundingClientRect().bottom;
    const footerTop = document.getElementById("site-footer").getBoundingClientRect().top;
    const margin = 12;
    this._panel.style.top = `${headerBottom + margin}px`;
    this._panel.style.bottom = `${window.innerHeight - footerTop + margin}px`;
  }

  // Called by the map's global "click" handler (a plain click while the
  // panel is open and this point isn't set yet) and by each marker's own
  // "dragend" - one path for both "place" and "adjust", so the route
  // recomputes the same way either time. Draggable so a placed point can
  // be nudged without starting over (setPoint always REPLACES any
  // previous marker/listener for that slot rather than adding a second
  // one, so a re-drag never accumulates duplicate handlers).
  setPoint(which, lngLat) {
    const isStart = which === "start";
    const color = isStart ? "#2E7D32" : "#C62828";
    const existingMarker = isStart ? routingStartMarker : routingEndMarker;
    if (existingMarker) existingMarker.remove();

    const marker = new maplibregl.Marker({ color, draggable: true }).setLngLat(lngLat).addTo(map);
    marker.on("dragend", () => {
      if (isStart) routingStart = marker.getLngLat(); else routingEnd = marker.getLngLat();
      this._updatePointRows();
      this._maybeAutoRoute();
      // moveend-driven syncUrlState (see that function) doesn't fire here
      // - dragging a marker doesn't move the CAMERA - so the URL's own
      // sy/sx/ey/ex would otherwise go stale the moment a point is
      // dragged, not just when it's first placed/cleared.
      syncUrlState();
    });

    if (isStart) { routingStart = lngLat; routingStartMarker = marker; }
    else { routingEnd = lngLat; routingEndMarker = marker; }

    this._updateCursor();
    this._updatePointRows();
    this._setStatus("");
    this._maybeAutoRoute();
    syncUrlState(); // same reasoning as the dragend handler above - placing a point doesn't necessarily move the camera either
  }

  _updatePointRows() {
    this._startRow.classList.toggle("is-set", !!routingStart);
    this._endRow.classList.toggle("is-set", !!routingEnd);
  }

  // Auto-routes as soon as both points exist - after the initial click
  // that completes the pair, and again after every marker drag ("così se
  // lo sposta quando vuole" - no button re-click needed either time).
  _maybeAutoRoute() {
    if (routingStart && routingEnd) this._findRoute();
  }

  // `loading` shows a spinner next to the text - routing involves a
  // network fetch of each candidate comune's routing graph plus an A*
  // search, real enough time (especially the first fetch, or a widen
  // retry pulling in more comuni) that a plain text line alone reads as
  // "did my click even register?" without it.
  _setStatus(text, loading = false) {
    this._statusText.textContent = text;
    this._statusSpinner.classList.toggle("hidden", !loading);
    this._status.classList.toggle("hidden", !text);
  }

  async _findRoute() {
    if (!routingStart || !routingEnd) return;
    this._setStatus(t("routingCalculating"), true);

    const comuniIndexData = await ensureComuniIndexLoaded();
    if (!comuniIndexData) {
      this._setStatus(t("routingNoCoverage"));
      return;
    }

    // Widen-and-retry: a route needing a comune beyond the tight
    // rectangle around start/end (e.g. via a third comune in between)
    // needs a wider candidate margin - bounded to a few attempts so a
    // genuinely out-of-coverage pair fails fast rather than pulling in
    // half of Italy. findRoute() itself can also return a PARTIAL result
    // (the destination is only reachable by crossing a non-cyclable gap -
    // see that function's own comment) - keep widening in case a bigger
    // margin turns it into a full route after all, but remember the
    // widest-margin partial result seen so far as a fallback in case none
    // ever does.
    const marginsDeg = [0.02, 0.08, 0.25];
    let bestPartial = null;
    for (const marginDeg of marginsDeg) {
      const slugs = candidateComuniForRoute(routingStart, routingEnd, comuniIndexData, marginDeg);
      if (slugs.size === 0) continue;

      const files = await Promise.all([...slugs].map((slug) => this._loadRoutingFile(slug)));
      const usable = files.filter(Boolean);
      if (!usable.length) continue;

      const cacheKey = usable.map((file) => file.slug).sort().join(",");
      let merged = mergedGraphCache.get(cacheKey);
      if (!merged) {
        merged = mergeRoutingGraphs(usable);
        mergedGraphCache.set(cacheKey, merged);
      }
      const { graph, coordByOsmId } = merged;
      const result = findRoute(routingStart, routingEnd, graph, coordByOsmId);
      if (result && !result.partial) {
        this._applyRoute(result);
        this._setStatus("");
        return;
      }
      if (result && result.partial) bestPartial = result;
    }
    if (bestPartial) {
      this._applyRoute(bestPartial);
      const lastCoord = bestPartial.feature.geometry.coordinates[bestPartial.feature.geometry.coordinates.length - 1];
      const remainingKm = approxMetersBetween(lastCoord, [routingEnd.lng, routingEnd.lat]) / 1000;
      this._setStatus(t("routingPartialRouteTemplate")(remainingKm.toFixed(1)));
      return;
    }
    this._setStatus(t("routingNoRoute"));
  }

  async _loadRoutingFile(slug) {
    if (routingFileCache.has(slug)) return routingFileCache.get(slug);
    try {
      const response = await fetch(new URL(`data/${slug}_routing.bin`, window.location.href));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const buffer = await response.arrayBuffer();
      const data = decodeRoutingGraphBinary(buffer);
      routingFileCache.set(slug, data);
      return data;
    } catch (error) {
      return null; // not cached - a later retry (e.g. a transient network error) can still succeed
    }
  }

  // Draws the route, frames it, and renders the summary/elevation - the
  // single call site everything downstream of a successful findRoute()
  // flows through, all fed by the same `runs` (buildRouteRuns).
  _applyRoute(result) {
    this._runs = buildRouteRuns(result.segments, result.feature.geometry.coordinates);
    const featureCollection = routeRunsToFeatureCollection(this._runs);
    map.getSource("routing-path").setData(featureCollection);

    // A partial result's own last coordinate is NOT where the rider
    // clicked (routingEndMarker stays there) - it's the closest point the
    // cyclable network actually reaches. Mark it distinctly so that gap
    // reads as "this is as far as you can bike", not as a second real
    // destination. Cleared whenever a route is FULL (or on _clear()).
    if (routingPartialEndMarker) { routingPartialEndMarker.remove(); routingPartialEndMarker = null; }
    if (result.partial) {
      const coords = result.feature.geometry.coordinates;
      const lastCoord = coords[coords.length - 1];
      routingPartialEndMarker = new maplibregl.Marker({ color: "#F9A825" })
        .setLngLat(lastCoord)
        .addTo(map);
    }

    // Frame the route only the FIRST time one appears - once the user is
    // dragging a marker to adjust it (setPoint -> _maybeAutoRoute ->
    // here, repeatedly), yanking the camera to fitBounds on every drag
    // would fight the very interaction they're doing.
    if (!routingHasEverRouted) {
      const bounds = boundsForFeatures(featureCollection.features);
      if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 60, maxZoom: MAX_MAP_ZOOM });
      routingHasEverRouted = true;
    }

    this._renderRouteSummary(this._runs);
    this._updateCompactPanelMaxHeight(); // the summary section (and its download buttons) just appeared/grew - recheck how much of it actually fits
    // Hidden until _renderElevationProfile's async terrain sampling
    // finishes (a few seconds) and fills it back in - a stale time from
    // the PREVIOUS route (e.g. after a drag) would otherwise sit there
    // looking current while the new one is still being computed.
    this._estimatedTimeEl.classList.add("hidden");
    this._renderElevationProfile(result.feature);
  }

  _renderRouteSummary(runs) {
    const totalKm = runs.reduce((sum, r) => sum + r.lengthM, 0) / 1000;
    this._summary.classList.remove("hidden");
    this._totalKmEl.textContent = `${t("routeTotalKm")}: ${totalKm.toFixed(1)} km`;

    // LTS mix bar - LTS_COLORS (the off-map palette, see ROUTE_LTS_COLORS'
    // own comment for why the map line itself uses a different one).
    const kmByLts = {};
    for (const run of runs) kmByLts[run.lts] = (kmByLts[run.lts] || 0) + run.lengthM / 1000;
    this._ltsBar.innerHTML = "";
    for (const lts of Object.keys(kmByLts).sort()) {
      const km = kmByLts[lts];
      const pct = (km / totalKm) * 100;
      const label = t("lts")[lts] || "";
      const descriptor = label.includes(" - ") ? label.split(" - ").slice(1).join(" - ") : label;
      this._appendBarSegment(
        this._ltsBar, pct, LTS_COLORS[lts] || LTS_FALLBACK_COLOR,
        t("routeLtsSegmentTemplate")(km.toFixed(1), Math.round(pct), descriptor),
      );
    }

    // Road-type mix bar - same 3-way split/order as renderFacilityLegend
    // (Street -> Cycleway -> Path), FACILITY_BAR_COLORS (not LTS_COLORS -
    // a different dimension on the same panel).
    const FACILITY_ORDER = [
      { code: 0, colorKey: "street", labelKey: "facilityStreet" },
      { code: 1, colorKey: "cycleway", labelKey: "facilityCycleway" },
      { code: 2, colorKey: "path", labelKey: "facilityPath" },
    ];
    const kmByFacility = {};
    for (const run of runs) kmByFacility[run.facilityCode] = (kmByFacility[run.facilityCode] || 0) + run.lengthM / 1000;
    this._facilityBar.innerHTML = "";
    this._facilityLegend.innerHTML = "";
    for (const { code, colorKey, labelKey } of FACILITY_ORDER) {
      const km = kmByFacility[code];
      if (!km) continue;
      const pct = (km / totalKm) * 100;
      const label = t(labelKey);
      const color = FACILITY_BAR_COLORS[colorKey];
      this._appendBarSegment(this._facilityBar, pct, color, t("routeFacilitySegmentTemplate")(km.toFixed(1), Math.round(pct), label));

      const legendRow = document.createElement("div");
      legendRow.className = "legend-item static";
      legendRow.innerHTML = `<span class="swatch" style="background:${color}"></span> ${label}`;
      this._facilityLegend.appendChild(legendRow);
    }
  }

  _appendBarSegment(bar, pct, color, tooltipText) {
    const segment = document.createElement("div");
    segment.className = "routing-bar-segment";
    segment.style.width = `${pct}%`;
    segment.style.background = color;
    segment.addEventListener("mouseenter", (e) => this._showBarTooltip(e, tooltipText));
    segment.addEventListener("mousemove", (e) => this._moveBarTooltip(e));
    segment.addEventListener("mouseleave", () => this._hideBarTooltip());
    bar.appendChild(segment);
  }

  _showBarTooltip(e, text) {
    this._barTooltip.textContent = text;
    this._barTooltip.classList.remove("hidden");
    this._moveBarTooltip(e);
  }

  // position:fixed (viewport-relative, see the CSS) rather than
  // positioned relative to the panel: the panel is narrow (260px) and
  // scrolls its own content (#routing-panel's overflow-y:auto), so a
  // tooltip positioned/clipped relative to it routinely got shoved off
  // the panel's own right edge and became unreadable - found via real
  // browser testing, not guessable from the CSS alone. Clamped to the
  // viewport instead, so it's always fully visible regardless of where in
  // the (possibly narrow, possibly scrolled) panel the segment sits.
  _moveBarTooltip(e) {
    const tooltip = this._barTooltip;
    tooltip.style.left = "0px";
    tooltip.style.top = "0px";
    const width = tooltip.offsetWidth;
    const height = tooltip.offsetHeight;
    const maxLeft = window.innerWidth - width - 8;
    const maxTop = window.innerHeight - height - 8;
    const left = Math.max(8, Math.min(e.clientX + 12, maxLeft));
    const top = Math.max(8, Math.min(e.clientY + 12, maxTop));
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }

  _hideBarTooltip() {
    this._barTooltip.classList.add("hidden");
  }

  // Samples elevation along the route from the already-loaded Mapterhorn
  // terrain tiles (map.queryTerrainElevation - needs an ACTIVE
  // map.setTerrain call, the raster-dem source alone isn't enough) and
  // draws a small SVG profile. Temporarily enables terrain if the user
  // hasn't turned "Terreno 3D" on, and restores whatever state it found -
  // no visible/lasting change for someone who never asked for 3D terrain.
  async _renderElevationProfile(feature) {
    this._elevationChart.innerHTML = "";
    const wasTerrainOn = terrainOn;
    if (!wasTerrainOn) map.setTerrain({ source: "mapterhorn-dem" });

    // Gives the DEM tiles for the just-fitBounds'd viewport a chance to
    // load - queryTerrainElevation returns null for an unloaded tile.
    await new Promise((resolve) => map.once("idle", resolve));

    const line = turf.lineString(feature.geometry.coordinates);
    const totalKm = turf.length(line, { units: "kilometers" });
    const sampleCount = 100;
    const points = [];
    for (let i = 0; i <= sampleCount; i++) {
      const km = (totalKm * i) / sampleCount;
      const along = i === sampleCount ? feature.geometry.coordinates[feature.geometry.coordinates.length - 1] : turf.along(line, km, { units: "kilometers" }).geometry.coordinates;
      points.push({ km, elev: map.queryTerrainElevation(along) });
    }
    this._interpolateMissingElevations(points);

    if (!wasTerrainOn) map.setTerrain(null);

    this._drawElevationSvg(points);
    this._renderEstimatedTime(points);
  }

  _renderEstimatedTime(points) {
    const totalMinutes = estimateRouteTimeMinutes(points);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = Math.round(totalMinutes % 60);
    this._estimatedTimeEl.textContent = t("routeEstimatedTimeTemplate")(hours, minutes);
    this._estimatedTimeEl.classList.remove("hidden");
  }

  _interpolateMissingElevations(points) {
    for (let i = 0; i < points.length; i++) {
      if (points[i].elev != null) continue;
      let before = i - 1;
      while (before >= 0 && points[before].elev == null) before--;
      let after = i + 1;
      while (after < points.length && points[after].elev == null) after++;
      if (before >= 0 && after < points.length) {
        const frac = (points[i].km - points[before].km) / (points[after].km - points[before].km);
        points[i].elev = points[before].elev + frac * (points[after].elev - points[before].elev);
      } else if (before >= 0) {
        points[i].elev = points[before].elev;
      } else if (after < points.length) {
        points[i].elev = points[after].elev;
      } else {
        points[i].elev = 0; // no terrain data anywhere along the route
      }
    }
  }

  _drawElevationSvg(points) {
    const width = 260;
    const height = 70;
    const padding = 4;
    const elevs = points.map((p) => p.elev);
    const minElev = Math.min(...elevs);
    const maxElev = Math.max(...elevs);
    const range = Math.max(maxElev - minElev, 1);
    const maxKm = points[points.length - 1].km || 1;

    const xFor = (km) => padding + (km / maxKm) * (width - 2 * padding);
    const yFor = (elev) => height - padding - ((elev - minElev) / range) * (height - 2 * padding);

    const linePoints = points.map((p) => `${xFor(p.km).toFixed(1)},${yFor(p.elev).toFixed(1)}`).join(" ");
    const areaPoints = `${xFor(0).toFixed(1)},${(height - padding).toFixed(1)} ${linePoints} ${xFor(maxKm).toFixed(1)},${(height - padding).toFixed(1)}`;

    this._elevationChart.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <polygon points="${areaPoints}" fill="#52514e" fill-opacity="0.15"></polygon>
        <polyline points="${linePoints}" fill="none" stroke="#52514e" stroke-width="2"></polyline>
        <text x="${padding}" y="10" font-size="9" fill="#52514e">${Math.round(maxElev)} m</text>
        <text x="${padding}" y="${height - 2}" font-size="9" fill="#52514e">${Math.round(minElev)} m</text>
        <line class="routing-elevation-crosshair" x1="0" y1="0" x2="0" y2="${height}" stroke="#999" stroke-width="1" visibility="hidden"></line>
      </svg>
    `;
    const svg = this._elevationChart.querySelector("svg");
    const crosshair = this._elevationChart.querySelector(".routing-elevation-crosshair");
    svg.addEventListener("mousemove", (e) => {
      const rect = svg.getBoundingClientRect();
      const relX = ((e.clientX - rect.left) / rect.width) * width;
      const km = Math.max(0, Math.min(maxKm, ((relX - padding) / (width - 2 * padding)) * maxKm));
      const nearest = points.reduce((best, p) => (Math.abs(p.km - km) < Math.abs(best.km - km) ? p : best), points[0]);
      const x = xFor(nearest.km).toFixed(1);
      crosshair.setAttribute("x1", x);
      crosshair.setAttribute("x2", x);
      crosshair.setAttribute("visibility", "visible");
      this._showBarTooltip(e, `${nearest.km.toFixed(1)} km - ${Math.round(nearest.elev)} m`);
    });
    svg.addEventListener("mouseleave", () => {
      crosshair.setAttribute("visibility", "hidden");
      this._hideBarTooltip();
    });
  }

  _clear() {
    routingStart = null;
    routingEnd = null;
    routingHasEverRouted = false;
    this._updateCursor();
    this._updatePointRows();
    if (routingStartMarker) { routingStartMarker.remove(); routingStartMarker = null; }
    if (routingEndMarker) { routingEndMarker.remove(); routingEndMarker = null; }
    if (routingPartialEndMarker) { routingPartialEndMarker.remove(); routingPartialEndMarker = null; }
    if (map.getSource("routing-path")) map.getSource("routing-path").setData(EMPTY_FEATURE_COLLECTION);
    this._runs = [];
    this._summary.classList.add("hidden");
    this._elevationChart.innerHTML = "";
    this._estimatedTimeEl.classList.add("hidden");
    this._hideBarTooltip();
    this._setStatus("");
    syncUrlState(); // clears routingStart/routingEnd above - drop sy/sx/ey/ex from the URL now, not whenever the next moveend happens to fire
  }
}

// Stacking order (each addControl call appends below the previous one
// at the same position): zoom -> fullscreen -> geocoder -> routing -> 3D -> PDF.
map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl(new maplibregl.FullscreenControl(), "top-right");
map.addControl(new GeocoderControl(), "top-right");
map.addControl(new RoutingControl(), "top-right");
map.addControl(new TerrainControl(), "top-right");
map.addControl(new PrintControl(), "top-right");
map.addControl(new ShareControl(), "top-right");
map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");

// The print stylesheet (see @media print above) resizes #map/#map-container
// to fill the printed page, but that's a CSS-only change - MapLibre keeps
// rendering at the WebGL canvas's last-known pixel size until told
// otherwise, so without an explicit resize() the printed map would be
// the on-screen framing letterboxed into the page rather than actually
// filling it. "afterprint" restores the interactive on-screen size the
// same way once the print dialog closes.
window.addEventListener("beforeprint", () => map.resize());
window.addEventListener("afterprint", () => map.resize());

document.querySelector(`input[name="basemap"][value="${currentBasemap}"]`).checked = true;
applyUiTranslations();

document.getElementById("lang-select").addEventListener("change", (e) => {
  currentLang = e.target.value;
  applyUiTranslations();
  renderLegend();
  renderFacilityLegend();
  updateZoomHint();
  if (gapModeOn) renderGapInterventions();
  updateGapToggleState();
  syncUrlState();
});

// setStyle() (below) replaces the whole style document, which drops any
// source/layer this page added on top of it - "style.load" fires after
// both the initial style AND every subsequent setStyle finish loading, so
// addDataLayers() (defined further down) re-adds them every time instead
// of only once on the first "load" event.
document.querySelectorAll('input[name="basemap"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    if (e.target.checked) {
      currentBasemap = e.target.value;
      map.setStyle(BASE_STYLES[currentBasemap]);
      syncUrlState();
    }
  });
});

// LTS colour palette: labels are NOT here, they come from
// I18N[currentLang].lts, so a language switch doesn't need to touch the
// colours at all.
//
// Traffic-light style green/green/orange/red, matching the reference
// legend the map is meant to echo. Checked against simulated
// deuteranopia/protanopia rather than assumed safe: a fully-saturated
// orange+red pair (e.g. #E07C1C/#E4322F) collapses under red-green CVD -
// LTS3 vs LTS4 drops to a simulated RGB distance of ~33-43, because orange
// and red are hue-neighbours that both project onto the same remaining
// blue-yellow axis. Darkening/desaturating both a step (LTS3 #C4681A,
// LTS4 #B7231F) recovers most of that separation (~48-55 simulated) while
// still clearing 3:1 contrast on white for all four classes. It's not as
// safe as the blue/violet scheme this replaced, but it's a floor-band
// pass rather than a fail, and the map has a second, colour-independent
// channel for the same distinction: the face icons' mouth shape
// (LTS_FACE_MOUTHS further down) still reads 1-4 correctly with no colour
// vision at all.
const LTS_COLORS = {
  "1": "#056F00", "2": "#2EA64D", "3": "#C4681A", "4": "#B7231F", "0": "#6B6B6B",
};
// Dark-basemap variants for the on-map line layer only (legend/popup/PDF
// swatches always show the LTS_COLORS above, regardless of basemap - see
// buildLtsLineColorExpression). All four of 1/3/4 dip under 3:1 contrast
// against the dark map style's ~#3B3B3B background and need lightening;
// "2" already clears it unswapped.
const LTS1_DARK_COLOR = "#1C7B14";
const LTS3_DARK_COLOR = "#E08A3E";
const LTS4_DARK_COLOR = "#E86A64";
const LTS_FALLBACK_COLOR = "#BDBDBD";

// Route-line-only LTS palette (RoutingControl's drawn path) - deliberately
// NOT LTS_COLORS. The base map already colours the whole street network
// green/orange/red by LTS; an overlaid route reusing those same hues would
// read as "just another LTS-coloured street", not "this is my selected
// route, and here's how stressful each part is". One hue (blue, matching
// this layer's original flat colour), four monotonic-lightness steps -
// darkest/most saturated = LTS 1 (lowest stress = highest intensity),
// palest = LTS 4. Off-map UI (the routing panel's own summary bar) keeps
// LTS_COLORS instead - no basemap to clash with there.
const ROUTE_LTS_COLORS = { "1": "#0D47A1", "2": "#1565C0", "3": "#1E88E5", "4": "#90CAF9" };

// Road-type mix bar colours (RoutingControl's summary panel) - 3 new
// categorical colours, deliberately not green/orange/red (already mean
// LTS on the very same panel). From the dataviz skill's reference
// palette, Street->Cycleway->Path order, validated
// (scripts under the skill's own tooling; light mode only - this app's
// panel chrome has no dark-mode CSS, only the map *basemap* has a "dark"
// style option, unrelated to panel background).
const FACILITY_BAR_COLORS = { street: "#2a78d6", cycleway: "#4a3aa7", path: "#1baf7a" };

// Progressive reveal of LTS classes by zoom, independent of (and applied on
// TOP of) the legend's own per-class toggle below (activeLts): a class
// hidden by zoom stays hidden even if the user has it checked in the
// legend, and a class the user unchecked stays hidden even once zoom would
// otherwise allow it. Without this, the whole-Italy overview at low zoom
// rendered every LTS class (including the busiest, highest-stress streets)
// all at once - a solid mass of colour rather than a legible skeleton.
// 1/2 (lowest stress) from MIN_STREETS_ZOOM, 3 joins from LTS_TIER3_MIN_ZOOM,
// the full 0-4 range only from COMUNE_SWAP_MIN_ZOOM on - which is also
// where per-comune full-detail tiles take over, so "everything" arrives
// exactly when the data backing it does too.
const LTS_TIER3_MIN_ZOOM = 8;
const LTS_CLASS_MIN_ZOOM = {
  "1": MIN_STREETS_ZOOM,
  "2": MIN_STREETS_ZOOM,
  "3": LTS_TIER3_MIN_ZOOM,
  "4": COMUNE_SWAP_MIN_ZOOM,
  "0": COMUNE_SWAP_MIN_ZOOM,
};
function ltsClassesAllowedAtZoom(zoom) {
  return Object.keys(LTS_COLORS).filter((key) => zoom >= LTS_CLASS_MIN_ZOOM[key]);
}

// One face per comfort level, drawn as inline SVG rather than a system
// emoji (😌🙂😐😣, the previous approach) - native emoji glyphs are
// fixed-colour pictographs the browser's colour-emoji font renders as
// bitmaps/COLR data, not text glyphs, so CSS `color` and even a `fill`
// attribute cannot recolour them. Drawing the face ourselves means the
// circle IS the LTS colour swatch - one indicator instead of a square +
// an uncoloured emoji side by side. "0"/fallback intentionally have no
// entry - "not allowed"/"unknown" aren't comfort levels in the 1-4 sense,
// so ltsIndicatorHtml() below falls back to the plain colour dot for them.
const LTS_FACE_MOUTHS = {
  "1": "M4 9.3 Q7 13 10 9.3",
  "2": "M4.5 9 Q7 11 9.5 9",
  "3": "M4.5 9.5 L9.5 9.5",
  "4": "M4.5 10.5 Q7 8 9.5 10.5",
};

function ltsFaceIcon(key, color) {
  const mouth = LTS_FACE_MOUTHS[key];
  if (!mouth) return null;
  return `<svg class="lts-face" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
    <circle cx="7" cy="7" r="6.5" fill="${color}" />
    <circle cx="4.7" cy="6" r="0.9" fill="white" />
    <circle cx="9.3" cy="6" r="0.9" fill="white" />
    <path d="${mouth}" fill="none" stroke="white" stroke-width="1.1" stroke-linecap="round" />
  </svg>`;
}

// Single entry point for every "LTS colour indicator" spot in the UI
// (legend, popup, priority-list rows) - keeps all three in sync without
// duplicating the SVG-vs-plain-dot fallback logic three times.
function ltsIndicatorHtml(key, color) {
  return ltsFaceIcon(key, color) || `<span class="swatch" style="background:${color}"></span>`;
}

// LTS_COLORS' own "1", "3" and "4" dip under 3:1 against the "dark"
// basemap - swapped for LTS1_DARK_COLOR/LTS3_DARK_COLOR/LTS4_DARK_COLOR
// here, but only for the on-map line layer: the legend/popup/PDF swatches
// (which read LTS_COLORS directly, always against #panel's white
// background - see styles.css) stay the documented colours regardless of
// basemap. "2" and "0" need no such swap - both already clear 3:1 on the
// light and dark basemap with their one shared value. Rebuilt fresh on
// every call rather than cached once, since addDataLayers() (which calls
// this) reruns on every basemap switch and currentBasemap may have changed
// since the last build.
function buildLtsLineColorExpression() {
  const darkOverrides = { "1": LTS1_DARK_COLOR, "3": LTS3_DARK_COLOR, "4": LTS4_DARK_COLOR };
  const expression = ["match", ["to-string", ["get", "lts"]]];
  for (const [key, color] of Object.entries(LTS_COLORS)) {
    const useColor = currentBasemap === "dark" && darkOverrides[key] ? darkOverrides[key] : color;
    expression.push(key, useColor);
  }
  expression.push(LTS_FALLBACK_COLOR);
  return expression;
}

// Legend doubles as a filter: click a class to hide/show it on the map.
// Every class starts active EXCEPT "0" (not cyclable at all - motorways,
// excluded private/service roads, etc.) - it's not part of the LTS 1-4
// comfort scale the map is actually about, and left on by default it was
// competing for attention with the streets a rider could choose between.
// Still one click away in the legend for anyone who wants to see what's
// excluded. Overridden entirely by the URL's ?lts= when present, so a
// shared/bookmarked link's chosen set (including "0" if it was explicitly
// on) always wins over this default.
const requestedLts = params.get("lts");
const activeLts = new Set(
  requestedLts
    ? requestedLts.split(",").filter((key) => key in LTS_COLORS)
    : Object.keys(LTS_COLORS).filter((key) => key !== "0"),
);

// Zoom-disabled entries (see LTS_CLASS_MIN_ZOOM above) render greyed out
// and un-clickable, with a tooltip naming the zoom they unlock at - same
// "not a real choice right now" treatment as .legend-item.static, just
// zoom-driven instead of permanent.
function renderLegend() {
  const legend = document.getElementById("legend");
  legend.innerHTML = "";
  const allowed = new Set(ltsClassesAllowedAtZoom(map.getZoom()));
  for (const [key, color] of Object.entries(LTS_COLORS)) {
    const zoomDisabled = !allowed.has(key);
    const item = document.createElement("div");
    item.className = "legend-item"
      + (zoomDisabled || !activeLts.has(key) ? " inactive" : "")
      + (zoomDisabled ? " zoom-disabled" : "");
    item.innerHTML = `${ltsIndicatorHtml(key, color)} ${t("lts")[key]}`;
    if (zoomDisabled) {
      item.title = t("legendZoomDisabledHint").replace("{zoom}", LTS_CLASS_MIN_ZOOM[key]);
    } else {
      item.addEventListener("click", () => {
        if (activeLts.has(key)) activeLts.delete(key); else activeLts.add(key);
        renderLegend();
        applyLtsFilter();
        syncUrlState();
      });
    }
    legend.appendChild(item);
  }
}

// Single source of truth for "which LTS classes actually render right now":
// the legend's own per-class toggle (activeLts) intersected with whichever
// classes the current zoom allows (ltsClassesAllowedAtZoom). Both
// applyLtsFilter (national + already-visible comune layers) and
// addComuneLayers (a comune layer just added) funnel through this so a
// newly added layer starts in sync instead of needing its own copy of the
// same logic.
function currentLtsFilterExpression() {
  const allowed = ltsClassesAllowedAtZoom(map.getZoom());
  const effective = [...activeLts].filter((key) => allowed.includes(key));
  return ["in", ["to-string", ["get", "lts"]], ["literal", effective]];
}

function applyLtsFilter() {
  const filter = currentLtsFilterExpression();
  for (const id of ltsLineLayerIds()) map.setFilter(id, filter);
  // LTS_PRIORITY_LAYER_ID mirrors the same zoom/legend filter, further
  // restricted to the two classes it exists to redraw on top - see its
  // own comment in addDataLayers.
  if (map.getLayer(LTS_PRIORITY_LAYER_ID)) {
    map.setFilter(LTS_PRIORITY_LAYER_ID, ["all", filter, ["in", ["to-string", ["get", "lts"]], ["literal", ["1", "2"]]]]);
  }
}

// Re-applies the zoom/legend filter and redraws the legend's disabled
// state whenever the current zoom crosses an LTS_CLASS_MIN_ZOOM boundary -
// tracked by tier signature rather than reacting to every "zoom" tick, so
// a scroll/pinch gesture that stays within one tier doesn't thrash the
// legend DOM or re-run setFilter on every frame.
let lastLtsZoomTierKey = null;
function handleLtsZoomTierChange() {
  const tierKey = ltsClassesAllowedAtZoom(map.getZoom()).join(",");
  if (tierKey === lastLtsZoomTierKey) return;
  lastLtsZoomTierKey = tierKey;
  applyLtsFilter();
  renderLegend();
}
map.on("zoom", handleLtsZoomTierChange);

// Not a filter (unlike the LTS colour legend above) - purely explains what
// the FACILITY_DASH_EXPRESSION patterns on the map mean, so it's static,
// no click handlers. Dasharray values here are scaled by an arbitrary
// preview stroke-width (3) purely for the little SVG icon - same ratios as
// FACILITY_*_DASH above (MapLibre's own units, multiples of the line's
// actual on-map width), just re-expressed in SVG pixels for a fixed-size
// preview.
function facilityDashIcon(dasharrayCss) {
  return `<svg width="28" height="10" viewBox="0 0 28 10" aria-hidden="true">
    <line x1="1" y1="5" x2="27" y2="5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-dasharray="${dasharrayCss}" />
  </svg>`;
}
function renderFacilityLegend() {
  const legend = document.getElementById("facility-legend");
  legend.innerHTML = "";
  const rows = [
    { icon: facilityDashIcon("6 6"), label: t("facilityStreet") },
    { icon: facilityDashIcon("1000 0"), label: t("facilityCycleway") },
    { icon: facilityDashIcon("1.5 4.5"), label: t("facilityPath") },
  ];
  for (const { icon, label } of rows) {
    const item = document.createElement("div");
    item.className = "legend-item static";
    item.innerHTML = `${icon} ${label}`;
    legend.appendChild(item);
  }
}

renderLegend();
renderFacilityLegend();

// OSM tag values -> a fragment that reads as a sentence once composed
// below ("Strada " + phrase, "Strada con " + phrase). A raw OSM value
// like "sett" or "opposite_track" means nothing to someone who isn't an
// OSM mapper - better to say nothing than show the tag verbatim, so
// values without a phrase here are simply omitted from the popup instead
// of falling back to the raw tag. Phrase dictionaries + sentence
// templates live in i18n.js (SURFACE_PHRASES/CYCLEWAY_PHRASES/SLOPE_PHRASES
// equivalent is I18N[lang].surface/cycleway/slope), one set per language.
function popupHtml(props) {
  const color = LTS_COLORS[String(props.lts ?? "")] || LTS_FALLBACK_COLOR;
  const ltsKey = String(props.lts ?? "");
  const ltsLabel = t("lts")[ltsKey] || t("lts").fallback;
  const surfacePhrase = t("surface")[props.surface];
  const cyclewayPhrase = t("cycleway")[props.cycleway_type];
  const slopePhrase = t("slope")[props.slope_class];
  // The `rule` code (e.g. "m6") is exported on every edge - looking up the
  // sentence in the current language instead of using `message` (baked in
  // Italian at compute-lts time) is what makes the rationale translatable.
  // Falls back to the baked message for any rule code missing from i18n.js.
  const ruleSentence = (props.rule && t("rules")[props.rule]) || props.message;

  // ltsbikeplan.domain.lts_rules.BikePathAnalysis.surface_penalty already
  // folds a rough surface into `lts` itself - this row just explains why
  // the number is higher than the base rule (props.rule) alone would
  // suggest, the same way the priority block explains is_gap_edge below.
  const surfacePenaltyDelta = Number(props.surface_penalty_delta);

  const extraRows = [
    surfacePhrase ? `<div>${t("surfaceTemplate")(surfacePhrase)}</div>` : "",
    surfacePenaltyDelta > 0 ? `<div>${t("surfacePenaltyTemplate")(surfacePenaltyDelta)}</div>` : "",
    cyclewayPhrase ? `<div>${t("cyclewayTemplate")(cyclewayPhrase)}</div>` : "",
  ].join("");

  // Same "is_gap_edge" flag driving the priority-interventions list
  // (see computeGapInterventions) - surfaced here too, right in the
  // popup, not just in the aggregated list, so clicking any one street
  // tells you on the spot whether/why it's flagged. 🔍 (not ⭐ - a star
  // reads as "featured/good," the opposite of "flagged for evaluation").
  // Excludes has_parallel_cycleway (domain/parallel_cycleway.py): a
  // stressful street running alongside its own separated cycle path
  // already has a low-stress alternative, so it's not worth flagging as a
  // priority even though its own LTS is high.
  const isPriority = String(props.is_gap_edge) === "true" && String(props.has_parallel_cycleway) !== "true";
  const priorityIcon = isPriority ? " \u{1F50D}" : "";
  const priorityBlock = isPriority
    ? `<div class="priority-note">${t("gapUrgency")[ltsKey] || ""} - ${t("centralityTemplate")(t("centrality")[props.centrality_class])}</div>`
    : "";

  return `
    <div class="lts-popup">
      <h3>${props.name || t("popupNoName")}${priorityIcon}</h3>
      <div><b>${t("popupComune")}:</b> ${props.comune || "-"}</div>
      <div>${ltsIndicatorHtml(ltsKey, color)} ${ltsLabel}</div>
      ${priorityBlock}
      ${extraRows}
      <details>
        <summary>${t("popupDetails")}</summary>
        <div><b>${t("popupMaxspeed")}:</b> ${props.maxspeed ?? "-"}</div>
        <div><b>${t("popupLanes")}:</b> ${props.lanes ?? "-"}</div>
        <div><b>${t("popupSlope")}:</b> ${props.slope != null ? Number(props.slope).toFixed(1) + "%" : "-"}${slopePhrase ? ` (${slopePhrase})` : ""}</div>
        <div><b>${t("popupLength")}:</b> ${props.length != null ? Number(props.length).toFixed(0) + " m" : "-"}</div>
        <div><b>${t("popupRule")}:</b> ${ruleSentence ?? "-"}</div>
        <div><b>OSM:</b> ${props.osmid != null ? `<a href="https://www.openstreetmap.org/way/${props.osmid}" target="_blank" rel="noopener noreferrer">${t("popupOsmLink")}</a>` : "-"}</div>
      </details>
    </div>
  `;
}

// Popup for a click on RoutingControl's drawn route (see the
// "routing-path-line" branch in the map's click handler below) - a
// deliberately smaller sibling of popupHtml above: km-so-far, street name,
// comune, and LTS in natural language, all off `routing-path`'s own
// FeatureCollection properties (see buildRouteRuns/_renderRoute in
// RoutingControl - startKm/endKm/name/lts/comuneSlug per run).
function routePopupHtml(props) {
  const ltsKey = String(props.lts ?? "");
  const color = LTS_COLORS[ltsKey] || LTS_FALLBACK_COLOR;
  const ltsLabel = t("lts")[ltsKey] || t("lts").fallback;
  const comuneLabel = props.comuneSlug ? String(props.comuneSlug).replace(/_/g, " ") : "-";
  const kmSoFar = Number(props.endKm ?? 0).toFixed(1);

  return `
    <div class="lts-popup">
      <h3>${props.name || t("popupNoName")}</h3>
      <div><b>${t("popupComune")}:</b> ${comuneLabel}</div>
      <div><b>${t("routeKmSoFar")}:</b> ${kmSoFar} km</div>
      <div>${ltsIndicatorHtml(ltsKey, color)} ${ltsLabel}</div>
    </div>
  `;
}

// If the URL already pins a camera position (a shared/bookmarked link),
// don't let the area's own fitBounds override it once data loads.
let hasFitBoundsOnce = hasExplicitView;

// Bolder for the comfortable classes so they stand out as "where it's
// good to bike"; thinner for the demanding ones so they recede visually.
// "0" (not cyclable) is thinner still - it's backdrop, not a route choice,
// so it should recede even behind LTS4. The trailing fallback (missing/
// unexpected `lts`) matches "0"'s width for the same reason.
//
// Flat, tier-specific widths from MIN_STREETS_ZOOM to COMUNE_SWAP_MIN_ZOOM,
// then a smooth ramp to the realistic z18 proportions - deliberately
// matching LTS_CLASS_MIN_ZOOM's own tiers (4-7 shows only LTS 1/2, 8-11
// adds LTS3, 12+ is the real per-comune data): each tier gets its OWN
// flat, exaggerated width rather than smoothly ramping toward the
// realistic z12+ proportions across it. Reported: at the whole-Italy
// overview the low-stress network is such a small fraction of total road
// length that even a smooth ramp toward "realistic" left it imperceptible
// for most of tiers 4-7/8-11 - a flat, deliberately non-proportionate
// width per tier (standard cartographic generalisation for a
// sparse-but-important feature class at small scale) keeps it visible
// through the WHOLE tier, not just its tail end near z12. Tier 8-11 also
// needs LTS1/2 to stay clearly ahead of LTS3 specifically, since that's
// the zoom range where LTS3 first joins them on screen (see
// LTS_CLASS_MIN_ZOOM) and could otherwise crowd them out by sheer
// quantity. From COMUNE_SWAP_MIN_ZOOM on, back to the original smooth,
// closer-to-real-proportions interpolation - individual streets are
// legible on their own by then, no exaggeration needed.
//
// A single top-level `interpolate` on zoom, not a `step` wrapping a
// nested `interpolate` - MapLibre rejects more than one zoom subexpression
// per expression ("Only one zoom-based 'step' or 'interpolate'
// subexpression may be used in an expression"), which made every
// lts-lines/lts-lines-priority addLayer() throw and silently drop the
// whole street layer (reported as "no data" for every comune, not just
// one). The two flat tiers are faked inside the interpolation by
// repeating each tier's value at a stop just below the next tier's
// start, so the ramp stays flat within a tier and only slopes on the
// real 12->18 segment.
const LTS_LINE_WIDTH = [
  "interpolate", ["linear"], ["zoom"],
  MIN_STREETS_ZOOM,
  ["match", ["to-string", ["get", "lts"]], "1", 2.5, "2", 2.0, "3", 0.5, "4", 0.4, "0", 0.3, 0.3],
  LTS_TIER3_MIN_ZOOM - 0.01,
  ["match", ["to-string", ["get", "lts"]], "1", 2.5, "2", 2.0, "3", 0.5, "4", 0.4, "0", 0.3, 0.3],
  LTS_TIER3_MIN_ZOOM,
  ["match", ["to-string", ["get", "lts"]], "1", 1.8, "2", 1.5, "3", 0.6, "4", 0.5, "0", 0.4, 0.4],
  COMUNE_SWAP_MIN_ZOOM - 0.01,
  ["match", ["to-string", ["get", "lts"]], "1", 1.8, "2", 1.5, "3", 0.6, "4", 0.5, "0", 0.4, 0.4],
  COMUNE_SWAP_MIN_ZOOM,
  ["match", ["to-string", ["get", "lts"]], "1", 1.0, "2", 1.2, "3", 0.8, "4", 0.6, "0", 0.4, 0.4],
  18,
  ["match", ["to-string", ["get", "lts"]], "1", 3.5, "2", 4.0, "3", 2.5, "4", 2.0, "0", 1.3, 1.3],
];
// Facility-type visual distinction - independent of the LTS colour/width
// channel above (which stays purely about stress severity): solid = street
// (mixed traffic, the default/majority case), long dash = a separated/
// dedicated cycleway, fine dots = an unpaved path or track - the near-
// universal cartographic convention for "informal/unsurfaced" (matches
// OSM-carto's own rendering). Driven by `highway` for the clear-cut cases
// (highway=cycleway/path/track/footway/bridleway) and by the same "s3"/
// "s7"/"s8" (physically-separated cycleway) and "s1"/"s2" (path/non-
// crossing footway) rule codes domain/lts_rules.py's is_separated_path
// already assigns, for a cycleway/path that reaches that classification
// via a cycleway:*/footway sub-tag rather than the highway tag itself.
// Dasharray units are multiples of the line's own width (MapLibre style
// spec), so the pattern scales automatically with LTS_LINE_WIDTH's own
// zoom/LTS-based sizing - no separate zoom interpolation needed here.
// Solid = a real physically-separated facility (dedicated cycleway);
// dashed = an ordinary street ridden in mixed traffic, the ambient
// default. Matches the reference legend's convention (and standard
// cartographic practice) - previously inverted, with the default street
// case drawn solid and the cycleway case dashed.
const FACILITY_CYCLEWAY_DASH = ["literal", [1, 0]];
// Gap widened from the original [2, 1] (reported by a real user testing
// on their own monitor: at the thin on-map line-width typical street
// segments actually render at - see LTS_LINE_WIDTH, often just ~1px at
// z12 - a 1-unit gap is only ~1px too, thin enough that anti-aliasing
// blurs it into looking almost solid, even though the SAME ratio reads
// as clearly dashed in the legend's own much thicker fixed-size preview
// (facilityDashIcon's "6 3", built at a 3px preview stroke-width - see
// its own comment). Equal dash/gap makes the empty interval unmistakable
// at any width instead of just scaling the existing ratio up.
const FACILITY_STREET_DASH = ["literal", [2, 2]];
const FACILITY_PATH_DASH = ["literal", [0.5, 1.5]];
const FACILITY_CYCLEWAY_RULES = ["literal", ["s3", "s7", "s8"]];
const FACILITY_PATH_RULES = ["literal", ["s1", "s2"]];
const FACILITY_PATH_HIGHWAYS = ["literal", ["path", "track", "footway", "bridleway"]];
const FACILITY_DASH_EXPRESSION = [
  "case",
  ["any",
    ["==", ["get", "highway"], "cycleway"],
    ["in", ["get", "rule"], FACILITY_CYCLEWAY_RULES],
  ],
  FACILITY_CYCLEWAY_DASH,
  ["any",
    ["in", ["get", "highway"], FACILITY_PATH_HIGHWAYS],
    ["in", ["get", "rule"], FACILITY_PATH_RULES],
  ],
  FACILITY_PATH_DASH,
  FACILITY_STREET_DASH,
];

const GAP_EDGE_WIDTH = 4;
// Shared by the base "gap-edges" layer and every per-comune gap-edges-<slug>
// layer added by addComuneLayers below - one filter definition, not one
// copy per source.
const GAP_EDGE_FILTER = [
  "all",
  ["==", ["to-string", ["get", "is_gap_edge"]], "true"],
  ["!=", ["to-string", ["get", "has_parallel_cycleway"]], "true"],
];

// Selection outline for a street focused from the priority list - yellow
// rather than the same purple already used for every "Tratti da
// valutare" edge (GAP_EDGE_WIDTH's colour above), so the one currently
// selected street reads unambiguously against every other purple-dashed
// street already on screen.
const GAP_SELECTION_COLOR = "#FFD60A";
const GAP_SELECTION_BUFFER_METERS = 3;
const EMPTY_FEATURE_COLLECTION = { type: "FeatureCollection", features: [] };

// Re-adds everything this page draws on top of the base style. Called
// after the initial style load AND after every subsequent setStyle() from
// the basemap switcher, since setStyle discards custom sources/layers
// that aren't part of the new style document.
function addDataLayers() {
  // First "symbol" layer in the current base style - place/road labels are
  // always symbol layers, regardless of which of the 4 basemaps
  // (light/summer/cycling/dark) is active. Passed as addLayer's beforeId
  // below so lts-lines/gap-edges render UNDER every label instead of
  // covering them - previously added with no beforeId at all, which
  // MapLibre puts on top of the whole style by default, burying region/
  // provincia/comune/suburb toponyms (reported: labels invisible under the
  // opaque LTS-colored lines). Recomputed on every call since style.load
  // also fires after setStyle() (basemap switch), and each basemap's
  // layer stack - and therefore its first symbol layer's id - differs.
  const firstSymbolLayerId = map.getStyle().layers.find((l) => l.type === "symbol")?.id;

  if (!map.getSource("lts")) {
    map.addSource("lts", { type: "vector", url: pmtilesUrl });
  }
  if (!map.getLayer("lts-lines")) {
    map.addLayer(
      {
        id: "lts-lines",
        type: "line",
        source: "lts",
        "source-layer": "lts",
        minzoom: MIN_STREETS_ZOOM,
        // Only for the merged "italia" tileset (capped at maxzoom 11, see
        // build_national_tiles.sh) - past COMUNE_SWAP_MIN_ZOOM, per-comune
        // sources take over (updateComuneOverlays) with the real z12-16
        // detail those comuni were built with; without this cap MapLibre
        // would keep this layer alive too by overzooming its last real (z11)
        // tile, rendering the same streets twice. A single-area page
        // (?area=Trento) has no comune source to hand off to, so it keeps
        // its own full range.
        ...(area === "italia" ? { maxzoom: COMUNE_SWAP_MIN_ZOOM } : {}),
        // Miter is MapLibre's default line-join: at low zoom, where many
        // short OSM road segments render just a few px apart, every heading
        // change between them shows up as a sharp point instead of a smooth
        // bend - reported as streets looking "too angular" at z11+. Round
        // joins/caps trace the same underlying geometry, just without the
        // spikes at each vertex.
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": buildLtsLineColorExpression(),
          "line-width": LTS_LINE_WIDTH,
          "line-dasharray": FACILITY_DASH_EXPRESSION,
        },
      },
      firstSymbolLayerId,
    );
  }
  // Redraws LTS 1/2 on top of the base "lts-lines" layer - a plain line
  // layer has no per-feature sort-key (that's symbol-layer-only in
  // MapLibre), so within ONE layer a crossing LTS3/4 street can still
  // paint over a low-stress one drawn earlier in the tile's own feature
  // order. This is a second, visually-identical layer restricted to
  // lts 1/2 (see applyLtsFilter below), added AFTER "lts-lines" so
  // MapLibre stacks it above - purely cosmetic, not part of
  // ltsLineLayerIds()/hit-testing, since "lts-lines" already covers the
  // same features for clicks/hover and duplicating that would just risk
  // a second popup/hover state to keep in sync for no benefit. minzoom
  // LTS_PRIORITY_MIN_ZOOM - see that const's own comment for why not
  // every zoom gets this treatment.
  if (!map.getLayer(LTS_PRIORITY_LAYER_ID)) {
    map.addLayer(
      {
        id: LTS_PRIORITY_LAYER_ID,
        type: "line",
        source: "lts",
        "source-layer": "lts",
        minzoom: LTS_PRIORITY_MIN_ZOOM,
        ...(area === "italia" ? { maxzoom: COMUNE_SWAP_MIN_ZOOM } : {}),
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": buildLtsLineColorExpression(),
          "line-width": LTS_LINE_WIDTH,
          "line-dasharray": FACILITY_DASH_EXPRESSION,
        },
      },
      firstSymbolLayerId,
    );
  }
  applyLtsFilter();

  // High-stress edges that touch a low-stress island
  // (domain/gap_analysis.py's is_gap_edge) - the literal segments to
  // evaluate for closing a gap, i.e. what feeds the "Tratti da valutare"
  // list. Excludes has_parallel_cycleway (domain/parallel_cycleway.py): a
  // stressful street running alongside its own separated cycle path for
  // most of its length already has a low-stress alternative, so it's not
  // a real gap to close even though its own LTS is high.
  //
  // Not drawn on the map at all (line-opacity: 0) - the purple dashed
  // overview this used to be was never explained anywhere in the UI and
  // wasn't earning its place; the real "this one is selected" signal is
  // the 3m yellow buffer from focusGapIntervention/applyGapHighlight
  // below, shown only once a street is actually picked from the list.
  // Still a real rendered layer, not visibility:none, though - it has to
  // stay queryable for computeGapInterventions()'s
  // queryRenderedFeatures() call to keep finding these edges at all.
  if (!map.getLayer("gap-edges")) {
    map.addLayer({
      id: "gap-edges",
      type: "line",
      source: "lts",
      "source-layer": "lts",
      minzoom: MIN_STREETS_ZOOM,
      // Same maxzoom cap as lts-lines above, same reason.
      ...(area === "italia" ? { maxzoom: COMUNE_SWAP_MIN_ZOOM } : {}),
      filter: GAP_EDGE_FILTER,
      layout: { visibility: gapModeOn ? "visible" : "none" },
      paint: {
        "line-color": "#7B2CBF",
        "line-width": GAP_EDGE_WIDTH * 0.6,
        "line-opacity": 0,
      },
    });
  }

  // Selection outline for a street focused from the "Tratti da valutare"
  // list (see focusGapIntervention/applyGapHighlight): a real geographic
  // buffer polygon (GAP_SELECTION_BUFFER_METERS, via turf.buffer on the
  // selected street's own GeoJSON geometry - see applyGapHighlight),
  // drawn as an outline only. A `line` layer never fills its geometry,
  // so "transparent fill" falls out of using one at all rather than
  // needing an explicit fill-opacity:0 on a separate fill layer.
  // Own GeoJSON source (not the "lts" vector tile source used
  // elsewhere): the buffer polygon is computed fresh client-side per
  // selection, not something baked into the tileset.
  if (!map.getSource("gap-edge-selected-buffer")) {
    map.addSource("gap-edge-selected-buffer", { type: "geojson", data: EMPTY_FEATURE_COLLECTION });
  }
  if (!map.getLayer("gap-edge-selected-buffer")) {
    map.addLayer({
      id: "gap-edge-selected-buffer",
      type: "line",
      source: "gap-edge-selected-buffer",
      layout: { visibility: gapModeOn ? "visible" : "none" },
      paint: {
        "line-color": GAP_SELECTION_COLOR,
        "line-width": 1.5,
        "line-dasharray": [2, 2],
      },
    });
  }

  // The route drawn by RoutingControl (web/routing.js's findRoute) - own
  // GeoJSON source, same reason as gap-edge-selected-buffer above: it's
  // computed fresh client-side per query, not part of any tileset.
  if (!map.getSource("routing-path")) {
    map.addSource("routing-path", { type: "geojson", data: EMPTY_FEATURE_COLLECTION });
  }
  if (!map.getLayer("routing-path-line")) {
    map.addLayer({
      id: "routing-path-line",
      type: "line",
      source: "routing-path",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: {
        "line-color": [
          "match", ["to-string", ["get", "lts"]],
          "1", ROUTE_LTS_COLORS["1"], "2", ROUTE_LTS_COLORS["2"], "3", ROUTE_LTS_COLORS["3"], "4", ROUTE_LTS_COLORS["4"],
          ROUTE_LTS_COLORS["4"],
        ],
        "line-width": 5,
      },
    });
  }

  // Mapterhorn open terrain tiles (Terrarium-encoded, Italy: 10m
  // resolution) - see mapterhorn.com/data-access. Same source used by
  // ltsbikeplan.services.dem_service for the slope calculation itself,
  // so the 3D relief shown here is consistent with what drove the LTS
  // classification.
  if (!map.getSource("mapterhorn-dem")) {
    map.addSource("mapterhorn-dem", {
      type: "raster-dem",
      tiles: ["https://tiles.mapterhorn.com/{z}/{x}/{y}.webp"],
      tileSize: 512,
      encoding: "terrarium",
      maxzoom: 13,
    });
  }
  if (terrainOn) {
    map.setTerrain({ source: "mapterhorn-dem", exaggeration: 1.3 });
    document.getElementById("terrain-toggle").classList.add("active");
  }

  if (gapModeOn) {
    applyGapHighlight();
    renderGapInterventions();
  }

  // Single-area views ("Trento", "Lavis", ...) zoom to that area's own
  // data. The merged "italia" tileset keeps the whole-Italy view above
  // instead - its bounds are just wherever areas happen to be computed
  // so far, which would give an arbitrary, shrinking-as-you-zoom-out crop
  // rather than the national context the user actually wants to see.
  // Only done once - switching basemap shouldn't reset the user's pan/zoom,
  // and never if the URL already restored a specific camera position.
  if (!hasFitBoundsOnce && area !== "italia") {
    hasFitBoundsOnce = true;
    tiles.getHeader().then((header) => {
      map.fitBounds(
        [[header.minLon, header.minLat], [header.maxLon, header.maxLat]],
        { padding: 40, duration: 0 },
      );
    });
  }

  // setStyle() (basemap switch) wipes every custom source/layer, including
  // any per-comune ones added by updateComuneOverlays below - re-add
  // whichever comuni were visible before the switch so zooming into a
  // comune's street-level detail then changing basemap doesn't silently
  // drop back to the coarser national overview.
  for (const slug of visibleComuneSlugs) addComuneLayers(slug);
}

map.on("style.load", addDataLayers);

// Adds one comune's own _lts.pmtiles as a source, with the same lts-lines/
// gap-edges layer pair addDataLayers sets up for the national tileset -
// idempotent, so both addDataLayers (after a basemap switch) and
// updateComuneOverlays (on pan/zoom) can call it freely.
function addComuneLayers(slug) {
  const sourceId = comuneSourceId(slug);
  if (map.getSource(sourceId)) return;

  const url = `pmtiles://${new URL(`data/${slug}_lts.pmtiles`, window.location.href)}`;
  const comuneTiles = new pmtiles.PMTiles(url.replace("pmtiles://", ""));
  protocol.add(comuneTiles);
  map.addSource(sourceId, { type: "vector", url });

  const firstSymbolLayerId = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
  map.addLayer(
    {
      id: comuneLinesLayerId(slug),
      type: "line",
      source: sourceId,
      "source-layer": "lts",
      minzoom: COMUNE_SWAP_MIN_ZOOM,
      layout: { "line-join": "round", "line-cap": "round" },
      paint: {
        "line-color": buildLtsLineColorExpression(),
        "line-width": LTS_LINE_WIDTH,
        "line-dasharray": FACILITY_DASH_EXPRESSION,
      },
    },
    firstSymbolLayerId,
  );
  map.addLayer({
    id: comuneGapLayerId(slug),
    type: "line",
    source: sourceId,
    "source-layer": "lts",
    minzoom: COMUNE_SWAP_MIN_ZOOM,
    filter: GAP_EDGE_FILTER,
    layout: { visibility: gapModeOn ? "visible" : "none" },
    paint: {
      "line-color": "#7B2CBF",
      "line-width": GAP_EDGE_WIDTH * 0.6,
      "line-opacity": 0,
    },
  });
  // New layer starts with no LTS-class filter applied - match whatever the
  // legend's toggles and the current zoom tier currently say (same filter
  // every other lts-lines layer already has).
  map.setFilter(comuneLinesLayerId(slug), currentLtsFilterExpression());
}

function removeComuneLayers(slug) {
  if (map.getLayer(comuneLinesLayerId(slug))) map.removeLayer(comuneLinesLayerId(slug));
  if (map.getLayer(comuneGapLayerId(slug))) map.removeLayer(comuneGapLayerId(slug));
  if (map.getSource(comuneSourceId(slug))) map.removeSource(comuneSourceId(slug));
}

// Below COMUNE_SWAP_MIN_ZOOM, drops every per-comune source (nothing to
// show at that zoom the national tileset doesn't already cover, and
// carrying them across a long pan back out would just waste memory). At
// or above it, adds/removes sources to match whichever comuni's bbox
// (web/data/comuni_index.json) overlaps the current viewport - a plain
// bbox check, not the real polygon: cheap, and precise enough for Italy's
// mostly-compact comuni (see build_comuni_index.py). No-op until
// comuniIndex has finished loading, or outside the "italia" view.
function updateComuneOverlays() {
  if (area !== "italia" || !comuniIndex) return;

  // map.addSource/addLayer/removeLayer/removeSource all throw "Style is
  // not done loading" if called before the style's own spec (sources/
  // layers JSON, sprite, glyphs - NOT tiles) has finished parsing -
  // normally not an issue (this mostly runs from a "moveend"-driven pan/
  // zoom, by which point that's long done), except for the very first
  // call, triggered as soon as comuni_index.json's fetch resolves, which
  // can race ahead of it. Retrying shortly after on exactly that error is
  // simpler and faster than waiting for any specific "is it ready yet"
  // event: `map.isStyleLoaded()` (this file used to gate on that) is the
  // wrong signal for it - it also waits for every source's in-flight TILE
  // requests, terrain DEM included, which measured 10-40s+ on a slow
  // mapterhorn.com response (reported: no street tiles for Palermo for a
  // long stretch after load, terrain-on urls hit this worst). The actual
  // throw only needs the style spec itself, which is typically ready
  // within a fraction of a second - this retry loop converges that fast
  // instead, with zero dependency on how long unrelated tile loading
  // takes. Retries indefinitely (no attempt cap): the same style-spec
  // race that triggers the first retry is gone within a beat, so in
  // practice this only ever loops a handful of times, right after load.
  try {
    if (map.getZoom() < COMUNE_SWAP_MIN_ZOOM) {
      if (visibleComuneSlugs.size === 0) return;
      for (const slug of visibleComuneSlugs) removeComuneLayers(slug);
      visibleComuneSlugs = new Set();
      return;
    }

    const bounds = map.getBounds();
    const west = bounds.getWest();
    const south = bounds.getSouth();
    const east = bounds.getEast();
    const north = bounds.getNorth();

    const wanted = new Set();
    for (const entry of comuniIndex) {
      const [minLon, minLat, maxLon, maxLat] = entry.bbox;
      if (maxLon >= west && minLon <= east && maxLat >= south && minLat <= north) wanted.add(entry.slug);
    }

    for (const slug of visibleComuneSlugs) if (!wanted.has(slug)) removeComuneLayers(slug);
    for (const slug of wanted) if (!visibleComuneSlugs.has(slug)) addComuneLayers(slug);
    visibleComuneSlugs = wanted;

    // Newly added layers above already got today's LTS-class filter
    // individually - this also re-syncs gap-mode visibility for them
    // (addComuneLayers already sets it at creation time too, this just
    // covers the layers that already existed before this call).
    applyLtsFilter();
  } catch (err) {
    if (!/style is not done loading/i.test((err && err.message) || "")) throw err;
    setTimeout(updateComuneOverlays, 150);
  }
}
map.on("moveend", updateComuneOverlays);

// Feedback while tiles are still loading (see #loading-indicator in
// index.html/styles.css) - the merged national tileset especially can take
// a while on a slow connection, and a blank map with no feedback reads as
// broken rather than "still working" (reported: users unsure whether to
// wait or reload). LOADING_SHOW_DELAY_MS debounces the show so a normal
// fast pan/zoom (tiles resolve well under that) never flickers it.
const LOADING_SHOW_DELAY_MS = 500;
let loadingShowTimer = null;

function showLoadingIndicator() {
  loadingShowTimer = null;
  document.getElementById("loading-indicator").classList.remove("hidden");
}

function hideLoadingIndicator() {
  clearTimeout(loadingShowTimer);
  loadingShowTimer = null;
  document.getElementById("loading-indicator").classList.add("hidden");
}

// Tracks whether the map is between a "dataloading" and its matching
// "idle" - i.e. genuinely fetching/parsing tiles right now, not just
// sitting at a zoom where clicking isn't available yet. Without this,
// #zoom-hint's "zoom in further to click a road" text sat on top of the
// map for however long italia_lts.pmtiles/comuni_index.json/a per-comune
// pmtiles took to load (real, sometimes several seconds - see
// build_national_tiles.sh's own size notes), reading as "nothing is
// happening, maybe broken" instead of "please wait" - reported live on
// stressinbici.it (zoomed into Verona, area=italia: blank map, only the
// zoom hint, for however long the comune swap's fetch took).
let dataIsLoading = false;

map.on("dataloading", () => {
  if (map.getZoom() < MIN_STREETS_ZOOM) return;
  dataIsLoading = true;
  updateZoomHint();
  if (loadingShowTimer == null && document.getElementById("loading-indicator").classList.contains("hidden")) {
    loadingShowTimer = setTimeout(showLoadingIndicator, LOADING_SHOW_DELAY_MS);
  }
});
map.on("idle", () => {
  dataIsLoading = false;
  hideLoadingIndicator();
  updateZoomHint();
});

// #zoom-hint takes the same top-center slot #loading-indicator uses, and
// the two are mutually exclusive by construction: whichever of this
// function's branches is live either shows the hint and hides the
// indicator, or (the dataIsLoading branch) hides the hint and leaves the
// indicator to the dataloading/idle handlers above - never both at once.
// Two hint tiers below MIN_CLICK_ZOOM: below MIN_STREETS_ZOOM streets
// aren't rendered at all yet (nothing to click regardless, and nothing
// loads either - see the early return above); between that and
// MIN_CLICK_ZOOM they ARE visible but too close together to click
// reliably (see the click handler's own MIN_CLICK_ZOOM guard) - UNLESS
// something is still actively loading for the current view, in which case
// the loading indicator takes the slot instead of a hint that would read
// as "nothing's happening" over a map that's still filling in. "zoom"
// (not "zoomend") for the same reason the cursor style updates on
// "mousemove" above rather than only once movement settles - the hint
// should track the gesture live, not wait for it to finish.
function updateZoomHint() {
  const zoom = map.getZoom();
  const hintEl = document.getElementById("zoom-hint");
  if (zoom < MIN_STREETS_ZOOM) {
    hintEl.textContent = t("zoomHint");
    hintEl.classList.remove("hidden");
    hideLoadingIndicator();
  } else if (zoom >= MIN_CLICK_ZOOM) {
    hintEl.classList.add("hidden");
  } else if (dataIsLoading) {
    hintEl.classList.add("hidden");
  } else {
    hintEl.textContent = t("zoomClickHint");
    hintEl.classList.remove("hidden");
  }
}
map.on("zoom", updateZoomHint);
updateZoomHint();

// Bound once on the whole map, not layer-scoped: with the italia view now
// able to have any number of per-comune lts-lines-<slug> layers active at
// once (see updateComuneOverlays), a fixed layer-id binding (map.on(type,
// "lts-lines", ...)) can't grow to cover layers added after the fact.
// Hit-testing via ltsLineLayerIds() at the event point instead always
// checks whichever set is live right now, base "lts-lines" included -
// same effective behaviour as the old per-layer binding, just not tied to
// one fixed id. Below MIN_CLICK_ZOOM, streets are too close together to
// click reliably - "mousemove" (not "mouseenter") re-checks the zoom on
// every move so the cursor updates correctly even if the user scroll-zooms
// without moving the mouse off the street they're hovering.
map.on("mousemove", (e) => {
  // A pending routing pick (see routingNextPickTarget) always wins over
  // the plain hover-pointer below - RoutingControl._updateCursor() sets
  // this same pin cursor on open/setPoint/close, but this handler runs on
  // every mouse move and would otherwise overwrite it right back to ""/
  // "pointer" the instant the mouse moves off a clickable feature.
  const pickTarget = routingNextPickTarget();
  if (pickTarget) {
    map.getCanvas().style.cursor = pickTarget === "start" ? START_CURSOR : END_CURSOR;
    return;
  }
  const overRoute = map.getLayer("routing-path-line")
    && map.queryRenderedFeatures(e.point, { layers: ["routing-path-line"] }).length > 0;
  const hovering = overRoute || (map.getZoom() >= MIN_CLICK_ZOOM
    && map.queryRenderedFeatures(e.point, { layers: ltsLineLayerIds() }).length > 0);
  map.getCanvas().style.cursor = hovering ? "pointer" : "";
});
map.on("click", (e) => {
  // While the routing panel is open and start/end isn't fully set yet, a
  // plain map click fills whichever is still missing - takes over the
  // click entirely, never falls through to the street-info popup below.
  // Once both are set, routingNextPickTarget() returns null and clicks
  // fall through normally (e.g. to the route-line click branch just
  // below, or a stray click does nothing - adjustments happen by
  // dragging the existing markers instead).
  const pickTarget = routingNextPickTarget();
  if (pickTarget && routingControlInstance) {
    routingControlInstance.setPoint(pickTarget, e.lngLat);
    return;
  }
  // The drawn route (when present) is the more specific thing being
  // clicked - it's rendered on top of the base LTS layer - so it's
  // queried first, at any zoom (not gated by MIN_CLICK_ZOOM: fitBounds
  // already framed the route, and it's a single small layer regardless
  // of zoom, not the dense full street network that gate exists for).
  if (map.getLayer("routing-path-line")) {
    const routeFeatures = map.queryRenderedFeatures(e.point, { layers: ["routing-path-line"] });
    if (routeFeatures.length) {
      new maplibregl.Popup({ maxWidth: "280px" })
        .setLngLat(e.lngLat)
        .setHTML(routePopupHtml(routeFeatures[0].properties))
        .addTo(map);
      return;
    }
  }
  if (map.getZoom() < MIN_CLICK_ZOOM) return;
  const features = map.queryRenderedFeatures(e.point, { layers: ltsLineLayerIds() });
  if (!features.length) return;
  new maplibregl.Popup({ maxWidth: "280px" })
    .setLngLat(e.lngLat)
    .setHTML(popupHtml(features[0].properties))
    .addTo(map);
});

document.getElementById("terrain-toggle").addEventListener("click", () => {
  terrainOn = !terrainOn;
  map.setTerrain(terrainOn ? { source: "mapterhorn-dem", exaggeration: 1.3 } : null);
  document.getElementById("terrain-toggle").classList.toggle("active", terrainOn);
  // Terrain exaggeration is nearly invisible from a straight-down view -
  // tilt the camera so the relief actually reads as 3D.
  map.easeTo({ pitch: terrainOn ? 60 : 0, duration: 800 });
  syncUrlState();
});

// Generic open/close wiring for header-triggered info panels (About,
// FAQ, Cookie/Privacy, Share) - purely informational, so intentionally
// NOT part of the URL-persisted view state (see syncUrlState below),
// unlike terrain/gap/basemap. Returns setOpen so callers that need to
// switch between two panels (the About->FAQ link right below) can drive
// both from outside. All four share the same centred, screen-covering
// .info-panel slot (styles.css) - only one should ever be open at once,
// so opening any of them closes whichever other one was open. `open`
// guards the mutual-close loop itself against re-entering (each closing
// call passes open=false, which skips this branch), not just against
// redundant no-op toggles.
const infoPanelSetters = [];
function setupInfoPanel(toggleId, panelId, closeId, onOpen) {
  const toggle = document.getElementById(toggleId);
  const panel = document.getElementById(panelId);
  function setOpen(open) {
    panel.classList.toggle("hidden", !open);
    toggle.classList.toggle("active", open);
    if (open) {
      for (const otherSetOpen of infoPanelSetters) {
        if (otherSetOpen !== setOpen) otherSetOpen(false);
      }
      if (onOpen) onOpen();
    }
  }
  infoPanelSetters.push(setOpen);
  toggle.addEventListener("click", () => setOpen(panel.classList.contains("hidden")));
  if (closeId) document.getElementById(closeId).addEventListener("click", () => setOpen(false));
  return setOpen;
}
const setAboutOpen = setupInfoPanel("about-toggle", "about-panel", "about-close");
const setFaqOpen = setupInfoPanel("faq-toggle", "faq-panel", "faq-close");
setupInfoPanel("privacy-toggle", "privacy-panel", "privacy-close");
// onOpen repopulates url/embed/social links fresh each time - see
// populateShareModal's own comment for why this can't just run once.
setupInfoPanel("share-toggle", "share-panel", "share-close", populateShareModal);

// "Dai un'occhiata alle FAQ" link inside the About body (see aboutBody in
// i18n.js) - event delegation on the parent, since #about-body's whole
// innerHTML is replaced on every applyUiTranslations() call (language
// switch), which would silently drop a listener bound directly to the
// inner <a>.
document.getElementById("about-body").addEventListener("click", (e) => {
  if (e.target.id !== "open-faq-link") return;
  e.preventDefault();
  setAboutOpen(false);
  setFaqOpen(true);
});

// --- Gap analysis: prioritized intervention list ---------------------
//
// Replaces the old per-"island" colouring/list: a raw connected-component
// grouping doesn't tell a comune anything actionable (one Trento island
// alone was 1374 raw OSM edge fragments with no way to prioritize among
// them). Instead this aggregates the is_gap_edge features currently on
// screen into one row per street name, ranked worst-first. lts-lines
// always paints with LTS_COLOR_EXPRESSION now - there is no island colour
// mode any more.
//
// Built with map.queryRenderedFeatures(), NOT Turf.js: same "read back
// what's already drawn" pattern the click popup already uses, zero new
// dependencies, scoped to exactly what the user can see.

// A single OSM way is graph-split into many edges at intersection nodes
// and shares one `osmid` across all of them - grouping by name, not
// osmid, is what turns e.g. Trento's "Strada forestale Fontana dei Gai"
// (331 distinct edges under one osmid) into a single row with a real
// total length instead of hundreds of near-zero fragments.
//
// Every edge in the export also appears as an exact duplicate row (same
// osmid AND identical geometry) - confirmed against data/Trento: 126924
// exported features are exactly 63462 distinct (osmid, geometry) pairs
// each appearing twice. A raw query result must be deduplicated before
// summing length, but NOT by osmid alone - that collapses genuinely
// distinct fragments (see above) far more than it fixes. Keying on
// osmid + the feature's own coordinates fixes the duplicate-row problem
// without discarding real fragments.
function dedupeFeatures(features) {
  const seen = new Set();
  const unique = [];
  for (const feature of features) {
    const key = `${feature.properties.osmid}:${JSON.stringify(feature.geometry.coordinates)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(feature);
  }
  return unique;
}

// LngLatBounds.extend() takes one [lng, lat] pair at a time. Source
// geometry is always LineString, but tippecanoe can clip a feature into a
// MultiLineString within a single tile when it crosses a tile edge more
// than once, so both shapes are handled rather than assumed.
function boundsForFeatures(features) {
  const bounds = new maplibregl.LngLatBounds();
  for (const feature of features) {
    const geom = feature.geometry;
    const lines = geom.type === "MultiLineString" ? geom.coordinates : [geom.coordinates];
    for (const line of lines) {
      for (const coord of line) bounds.extend(coord);
    }
  }
  return bounds;
}

// Same reasoning as MIN_CLICK_ZOOM on lts-lines: below this zoom there
// are too many edges on screen for a per-street aggregate to mean
// anything, and queryRenderedFeatures would just be slow for no benefit.
function belowGapZoom() {
  return map.getZoom() < MIN_CLICK_ZOOM;
}

// Aggregates the on-screen is_gap_edge features into one row per street
// name, sorted worst-first (highest LTS, then highest betweenness
// centrality - see domain/network_centrality.py - then longest total gap
// length). Centrality is what turns "this street has high LTS" (obvious
// from the map colour alone) into "this street is also a mandatory
// passage many trips are forced through" - the actual reason it's worth
// prioritizing. Unnamed fragments (~40% of gap-edge length in the
// Trento/Lavis exports) are left out of the LIST - "un tratto senza
// nome" isn't actionable - but stay visible on the map via the
// gap-edges layer regardless.
function computeGapInterventions() {
  const layers = gapEdgeLayerIds();
  if (!layers.length) return [];
  const unique = dedupeFeatures(map.queryRenderedFeatures({ layers }));

  const byName = new Map();
  for (const feature of unique) {
    const name = feature.properties.name;
    if (!name) continue;
    const lts = Number(feature.properties.lts) || 0;
    const length = Number(feature.properties.length) || 0;
    const centrality = Number(feature.properties.centrality) || 0;
    let entry = byName.get(name);
    if (!entry) {
      entry = { name, lts, length: 0, centrality, centralityClass: feature.properties.centrality_class, features: [] };
      byName.set(name, entry);
    }
    // A street can carry more than one LTS/centrality value across its
    // fragments; keep the worst/highest so the row reflects its
    // least-comfortable, most-structurally-important stretch.
    entry.lts = Math.max(entry.lts, lts);
    entry.length += length;
    if (centrality >= entry.centrality) {
      entry.centrality = centrality;
      entry.centralityClass = feature.properties.centrality_class;
    }
    entry.features.push(feature);
  }

  // LTS first (still the more severe signal - a physically stressful
  // street), then centrality (how much avoiding it costs other people -
  // the "why does this matter" the raw LTS number alone can't explain),
  // then length as a final tiebreak.
  return [...byName.values()].sort((a, b) => b.lts - a.lts || b.centrality - a.centrality || b.length - a.length);
}

// The list is scoped to whatever's on screen, but a wide view over a
// dense area can still turn up far more streets than fit in the panel -
// paginated (not an internally scrolling list) so the panel itself stays
// a fixed, predictable size. Page resets only when the current page no
// longer exists in the new result (e.g. a pan/zoom shrinks the list) -
// preserved otherwise, so paging to page 2 doesn't get silently undone
// by the same moveend/idle-triggered re-render that recomputes the list
// on every map interaction.
const GAP_LIST_PAGE_SIZE = 10;
let gapListPage = 1;

function renderGapPager(totalPages) {
  const pager = document.getElementById("gap-pager");
  pager.innerHTML = "";
  if (totalPages <= 1) return;

  const prev = document.createElement("button");
  prev.type = "button";
  prev.textContent = "‹";
  prev.disabled = gapListPage <= 1;
  prev.addEventListener("click", () => {
    gapListPage -= 1;
    renderGapInterventions();
  });

  const label = document.createElement("span");
  label.id = "gap-pager-label";
  label.textContent = `${gapListPage} / ${totalPages}`;

  const next = document.createElement("button");
  next.type = "button";
  next.textContent = "›";
  next.disabled = gapListPage >= totalPages;
  next.addEventListener("click", () => {
    gapListPage += 1;
    renderGapInterventions();
  });

  pager.append(prev, label, next);
}

function renderGapInterventions() {
  const list = document.getElementById("gap-list");
  const pager = document.getElementById("gap-pager");
  if (belowGapZoom()) {
    list.innerHTML = `<p>${t("gapZoomHint")}</p>`;
    pager.innerHTML = "";
    return;
  }
  const interventions = computeGapInterventions();
  list.innerHTML = "";
  if (!interventions.length) {
    list.innerHTML = `<p>${t("gapEmpty")}</p>`;
    pager.innerHTML = "";
    return;
  }

  const totalPages = Math.max(1, Math.ceil(interventions.length / GAP_LIST_PAGE_SIZE));
  gapListPage = Math.min(gapListPage, totalPages);
  const pageStart = (gapListPage - 1) * GAP_LIST_PAGE_SIZE;
  const pageItems = interventions.slice(pageStart, pageStart + GAP_LIST_PAGE_SIZE);

  pageItems.forEach((item) => {
    const row = document.createElement("div");
    row.className = "gap-item";
    const color = LTS_COLORS[String(item.lts)] || LTS_FALLBACK_COLOR;
    const urgency = t("gapUrgency")[String(item.lts)] || "";
    const centralityPhrase = t("centrality")[item.centralityClass];
    const explainLine = centralityPhrase
      ? `<div class="gap-item-explain">${urgency ? urgency + " - " : ""}${t("centralityTemplate")(centralityPhrase)}</div>`
      : "";
    row.innerHTML = `
      <div class="gap-item-main">${ltsIndicatorHtml(String(item.lts), color)} ${item.name}: ${(item.length / 1000).toFixed(2)} km (LTS ${item.lts})</div>
      ${explainLine}
    `;
    row.addEventListener("click", () => focusGapIntervention(item));
    list.appendChild(row);
  });

  renderGapPager(totalPages);
}

// Highlighted street persists across live-refreshes (moveend/idle/zoom
// just recompute the list; they shouldn't wipe the user's current
// selection), so the selection lives outside computeGapInterventions().
// selectedGapFeatures (the raw GeoJSON geometries, not just the name) is
// what applyGapHighlight buffers - kept alongside the name rather than
// re-querying the map for it on every call.
let selectedGapName = null;
let selectedGapFeatures = null;

// A real geographic buffer (turf.buffer, GAP_SELECTION_BUFFER_METERS)
// around the selected street's own geometry - not a stylistic wider
// line, an actual polygon at a fixed real-world distance regardless of
// zoom. Buffers each fragment separately rather than merging them first:
// a street is usually split into several OSM way fragments (same
// reasoning as dedupeFeatures/computeGapInterventions above), and their
// individual buffers overlap seamlessly wherever the fragments are
// adjacent, so the visual result is the same as buffering one merged
// line without needing a turf.union pass first.
function selectionBufferGeoJSON(features) {
  if (!features || !features.length) return EMPTY_FEATURE_COLLECTION;
  const lines = {
    type: "FeatureCollection",
    features: features.map((f) => ({ type: "Feature", properties: {}, geometry: f.geometry })),
  };
  return turf.buffer(lines, GAP_SELECTION_BUFFER_METERS, { units: "meters" });
}

function applyGapHighlight() {
  const source = map.getSource("gap-edge-selected-buffer");
  if (!source) return;
  source.setData(selectionBufferGeoJSON(selectedGapFeatures));
}

function focusGapIntervention(item) {
  selectedGapName = item.name;
  selectedGapFeatures = item.features;
  const bounds = boundsForFeatures(item.features);
  // Capped at MAX_MAP_ZOOM (21, the map's own hard ceiling) - without any
  // cap a tiny bounding box (a 20m fragment) would ask fitBounds for an
  // even higher zoom, which MapLibre just clamps to the ceiling anyway,
  // so this is more "make the cap explicit" than a real behaviour change.
  if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 60, maxZoom: MAX_MAP_ZOOM });
  applyGapHighlight();
}

function setGapMode(on) {
  gapModeOn = on;
  document.getElementById("gap-panel").classList.toggle("open", on);
  document.getElementById("gap-toggle").classList.toggle("active", on);
  for (const id of gapEdgeLayerIds()) {
    map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
  }
  if (map.getLayer("gap-edge-selected-buffer")) {
    map.setLayoutProperty("gap-edge-selected-buffer", "visibility", on ? "visible" : "none");
  }
  if (on) {
    gapListPage = 1;
    renderGapInterventions();
  } else {
    selectedGapName = null;
    selectedGapFeatures = null;
    applyGapHighlight();
  }
  syncUrlState();
}

// Below MIN_CLICK_ZOOM the button is visually disabled (see
// updateGapToggleState) but this guard covers any programmatic click too.
document.getElementById("gap-toggle").addEventListener("click", () => {
  if (belowGapZoom()) return;
  setGapMode(!gapModeOn);
});

// Bound once on "zoom", which fires for scroll/pinch, the +/- control, AND
// programmatic fitBounds/flyTo/easeTo - one binding covers every way the
// camera can cross MIN_CLICK_ZOOM, matching the existing "bind once, not
// inside addDataLayers" pattern used for the lts-lines click/hover
// handlers above.
function updateGapToggleState() {
  const disabled = belowGapZoom();
  const toggle = document.getElementById("gap-toggle");
  toggle.disabled = disabled;
  toggle.title = disabled ? t("gapZoomHint") : "";
  if (gapModeOn) renderGapInterventions();
}
map.on("zoom", updateGapToggleState);
updateGapToggleState(); // default view starts at zoom 5.2, well below threshold

// --- URL state -------------------------------------------------------

// Keeps the address bar mirroring everything that affects what's on
// screen, so a copied/bookmarked link reopens to the same view. Uses
// replaceState (not pushState) so panning/zooming doesn't spam browser
// history - only an explicit navigation (back button from another page)
// should leave this view.
// Shared by syncUrlState (writes it into the actual address bar) and
// ShareControl's "Condividi" button (packs the same object into a
// compact code instead - see encodeShareState near the top of the file).
// Only the routing keys are conditional (sy/sx/ey/ex - omitted when no
// route is active); everything else always has a value, matching what
// the address bar has always carried.
function currentUrlState() {
  const center = map.getCenter();
  const state = {
    area,
    z: map.getZoom().toFixed(2),
    y: center.lat.toFixed(5),
    x: center.lng.toFixed(5),
    p: map.getPitch().toFixed(0),
    b: map.getBearing().toFixed(0),
    bg: currentBasemap,
    lts: [...activeLts].sort().join(","),
    t: terrainOn ? "1" : "0",
    g: gapModeOn ? "1" : "0",
    lang: currentLang,
  };
  if (routingStart && routingEnd) {
    state.sy = routingStart.lat.toFixed(5);
    state.sx = routingStart.lng.toFixed(5);
    state.ey = routingEnd.lat.toFixed(5);
    state.ex = routingEnd.lng.toFixed(5);
  }
  return state;
}

// Keeps the address bar mirroring everything that affects what's on
// screen, so a copied/bookmarked link reopens to the same view. Uses
// replaceState (not pushState) so panning/zooming doesn't spam browser
// history - only an explicit navigation (back button from another page)
// should leave this view.
function syncUrlState() {
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(currentUrlState())) url.searchParams.set(key, value);
  // Drop the old long-form keys (see paramFloat/paramFlag's own comment -
  // still READ for backward compatibility) and the one-shot share code so
  // neither lingers alongside the short form this function just wrote.
  for (const staleKey of ["zoom", "lat", "lon", "pitch", "bearing", "terrain", "gap", "c"]) {
    url.searchParams.delete(staleKey);
  }
  if (!routingStart || !routingEnd) {
    for (const key of ["sy", "sx", "ey", "ex"]) url.searchParams.delete(key);
  }
  history.replaceState(null, "", url);
}

map.on("moveend", syncUrlState);
// moveend fires as soon as panning stops, but queryRenderedFeatures only
// sees tiles already loaded - a big pan into unloaded territory needs
// "idle" (fires once rendering has fully settled) too, or the list would
// silently under-report with no further update once tiles arrive.
map.on("moveend", () => { if (gapModeOn) renderGapInterventions(); });
map.on("idle", () => { if (gapModeOn) renderGapInterventions(); });

// Soft counterpart to MAX_BOUNDS (see the comment up at the map
// constructor): once a gesture ends, ease back within MAX_BOUNDS if the
// view has actually drifted outside it - a pure pan, keeping whatever
// zoom the user was at (dragging back from wherever they scrolled off to,
// not re-fitting the whole box and yanking the zoom level out from under
// them). Re-checked on every moveend rather than cached, so it still
// accounts for its own correction (which fires its own moveend) and for
// window resizes changing the fit zoom.
function clampToMaxBounds() {
  // Only case a pan alone can't fix: zoomed out far enough that MAX_BOUNDS
  // no longer fills the viewport in some direction, so there's no
  // position where the view wouldn't show outside it - has to zoom back
  // in too. cameraForBounds gives the exact zoom where it (just) does.
  const fitZoom = map.cameraForBounds(MAX_BOUNDS, { padding: 0 }).zoom;
  if (map.getZoom() < fitZoom - 0.01) {
    map.fitBounds(MAX_BOUNDS, { padding: 0, animate: true, duration: 600 });
    return;
  }
  const view = map.getBounds();
  let dLng = 0, dLat = 0;
  if (view.getWest() < MAX_BOUNDS.getWest()) dLng = MAX_BOUNDS.getWest() - view.getWest();
  else if (view.getEast() > MAX_BOUNDS.getEast()) dLng = MAX_BOUNDS.getEast() - view.getEast();
  if (view.getSouth() < MAX_BOUNDS.getSouth()) dLat = MAX_BOUNDS.getSouth() - view.getSouth();
  else if (view.getNorth() > MAX_BOUNDS.getNorth()) dLat = MAX_BOUNDS.getNorth() - view.getNorth();
  if (dLng !== 0 || dLat !== 0) {
    const center = map.getCenter();
    map.easeTo({ center: [center.lng + dLng, center.lat + dLat], duration: 600 });
  }
}
map.on("moveend", clampToMaxBounds);

// Restores a route from a shared/bookmarked link (sy/sx/ey/ex - see
// currentUrlState/syncUrlState). Deliberately placed HERE, at the very
// end of the script, not right after RoutingControl is added further up
// - setPoint() below calls syncUrlState() (see its own comment), which
// reads `activeLts`, a `const` declared later in the file than
// RoutingControl's own map.addControl() call; calling it that early threw
// "Cannot access 'activeLts' before initialization" (found via a real
// share-link round-trip, not guessable from reading either function in
// isolation). setPoint() itself triggers the actual A* search once both
// are set (_maybeAutoRoute), same as a real user click would; opens the
// panel too, so the restored route (and its summary) is immediately
// visible instead of only the drawn line.
if (params.has("sy") && params.has("sx") && params.has("ey") && params.has("ex")) {
  const restoreRouteFromUrl = () => {
    routingControlInstance._open();
    routingControlInstance.setPoint("start", { lng: parseFloat(params.get("sx")), lat: parseFloat(params.get("sy")) });
    routingControlInstance.setPoint("end", { lng: parseFloat(params.get("ex")), lat: parseFloat(params.get("ey")) });
  };
  // setPoint -> _applyRoute needs the "routing-path" SOURCE, added by
  // addDataLayers() on "style.load" - the style is still loading
  // asynchronously at this point on a fresh page load (this whole script
  // runs synchronously well before that fires), so calling setPoint this
  // early threw "Cannot read properties of undefined (reading 'setData')"
  // - same style-not-ready race already found/fixed for
  // updateComuneOverlays, same fix here.
  if (map.isStyleLoaded()) restoreRouteFromUrl();
  else map.once("style.load", restoreRouteFromUrl);
}

syncUrlState();
