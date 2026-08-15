// Below this zoom, individual streets are too close together on screen to
// click reliably, and the point of a click is to inspect ONE street - a
// single named constant so the threshold is easy to retune later.
const MIN_CLICK_ZOOM = 14;

// Area to load: web/index.html?area=<area_slug>, matching the file
// scripts/build_tiles.sh writes to web/data/<area_slug>_lts.pmtiles.
// "italia" (default) is the merged tileset from build_national_tiles.sh -
// it starts at a whole-Italy view rather than zooming to whatever areas
// happen to be computed so far (see the fitBounds guard below).
const params = new URLSearchParams(window.location.search);
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
  document.getElementById("bg-light-label").textContent = t("bgLight");
  document.getElementById("bg-summer-label").textContent = t("bgSummer");
  document.getElementById("bg-cycling-label").textContent = t("bgCycling");
  document.getElementById("bg-dark-label").textContent = t("bgDark");
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
const hasExplicitView = params.has("zoom") || params.has("lat") || params.has("lon");
const initialZoom = params.has("zoom") ? parseFloat(params.get("zoom")) : 5.2;
const initialLat = params.has("lat") ? parseFloat(params.get("lat")) : 42.3;
const initialLon = params.has("lon") ? parseFloat(params.get("lon")) : 12.5;
const initialPitch = params.has("pitch") ? parseFloat(params.get("pitch")) : 0;
const initialBearing = params.has("bearing") ? parseFloat(params.get("bearing")) : 0;
let currentBasemap = params.get("bg") in BASE_STYLES ? params.get("bg") : "dark";
let terrainOn = params.get("terrain") === "1";
let gapModeOn = params.get("gap") === "1";
document.getElementById("gap-panel").classList.toggle("open", gapModeOn);
document.getElementById("gap-toggle").classList.toggle("active", gapModeOn);

// 21 is the real ceiling for this map - the basemap styles top out there,
// so anything past it is just an empty/blank overzoom with no new detail.
// Set explicitly (not left to MapLibre's own default of 22) so every
// zoom-driving call - scroll/pinch, the +/- control, and any programmatic
// fitBounds/flyTo without its own maxZoom override - respects the same
// real limit.
const MAX_MAP_ZOOM = 21;

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
// is looking at one specific comune within it. Reads the "comune" property
// every edge already carries (compute_lts.py sets it from AreaSpec.name)
// off whatever's currently rendered on screen - the same
// queryRenderedFeatures() approach computeGapInterventions() uses. A
// single comune dominating most of what's visible gets named; a
// wider/mixed view (several comuni, or genuinely zoomed out to a
// national/regional scale) falls back to "Italia" rather than naming
// whichever comune happens to have the most edges in a roughly even mix.
function currentAreaLabel() {
  if (area !== "italia") return area.replace(/_/g, " ");
  if (!map.getLayer("lts-lines")) return "Italia";

  const features = map.queryRenderedFeatures({ layers: ["lts-lines"] });
  if (!features.length) return "Italia";

  const counts = {};
  for (const feature of features) {
    const comune = feature.properties.comune;
    if (comune) counts[comune] = (counts[comune] || 0) + 1;
  }
  const ranked = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!ranked.length) return "Italia";

  const [topComune, topCount] = ranked[0];
  return topCount / features.length > 0.6 ? topComune : "Italia";
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
    // A drawn PDF-file icon (document + folded corner + red "PDF" band,
    // same red as the LTS 4 swatch) rather than an emoji - no Unicode
    // emoji actually depicts a PDF specifically, and a generic document/
    // printer glyph doesn't say "this exports a PDF" as directly.
    button.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 2 H14 L19 7 V22 H5 Z" fill="#f5f5f5" stroke="#888" stroke-width="1" stroke-linejoin="round" />
      <path d="M14 2 L19 7 H14 Z" fill="#cccccc" />
      <rect x="4" y="13" width="15" height="6" rx="1" fill="#D1495B" />
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
  }

  _close() {
    this._panel.classList.add("hidden");
    this._button.classList.remove("active");
    this._hideResults();
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

// Stacking order (each addControl call appends below the previous one
// at the same position): zoom -> fullscreen -> geocoder -> 3D -> PDF.
map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl(new maplibregl.FullscreenControl(), "top-right");
map.addControl(new GeocoderControl(), "top-right");
map.addControl(new TerrainControl(), "top-right");
map.addControl(new PrintControl(), "top-right");
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

// LTS colour palette: muted teal/soft-green for the comfortable classes,
// progressively more saturated orange/brick-red for the demanding ones -
// labels are NOT here, they come from I18N[currentLang].lts, so a
// language switch doesn't need to touch the colours at all.
const LTS_COLORS = {
  "1": "#2A9D8F", "2": "#A8C957", "3": "#F4A261", "4": "#D1495B", "0": "#555555",
};
const LTS_FALLBACK_COLOR = "#BDBDBD";

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

const LTS_COLOR_EXPRESSION = ["match", ["to-string", ["get", "lts"]]];
for (const [key, color] of Object.entries(LTS_COLORS)) {
  LTS_COLOR_EXPRESSION.push(key, color);
}
LTS_COLOR_EXPRESSION.push(LTS_FALLBACK_COLOR);

// Legend doubles as a filter: click a class to hide/show it on the map.
// All classes start active (or whatever the URL's ?lts= says); the layer
// filter and legend re-render on every toggle so they can't disagree
// about what's currently shown.
const requestedLts = params.get("lts");
const activeLts = new Set(
  requestedLts ? requestedLts.split(",").filter((key) => key in LTS_COLORS) : Object.keys(LTS_COLORS),
);

function renderLegend() {
  const legend = document.getElementById("legend");
  legend.innerHTML = "";
  for (const [key, color] of Object.entries(LTS_COLORS)) {
    const item = document.createElement("div");
    item.className = "legend-item" + (activeLts.has(key) ? "" : " inactive");
    item.innerHTML = `${ltsIndicatorHtml(key, color)} ${t("lts")[key]}`;
    item.addEventListener("click", () => {
      if (activeLts.has(key)) activeLts.delete(key); else activeLts.add(key);
      renderLegend();
      applyLtsFilter();
      syncUrlState();
    });
    legend.appendChild(item);
  }
}

function applyLtsFilter() {
  if (!map.getLayer("lts-lines")) return;
  map.setFilter("lts-lines", ["in", ["to-string", ["get", "lts"]], ["literal", [...activeLts]]]);
}

renderLegend();

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

  const extraRows = [
    surfacePhrase ? `<div>${t("surfaceTemplate")(surfacePhrase)}</div>` : "",
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
      </details>
    </div>
  `;
}

// If the URL already pins a camera position (a shared/bookmarked link),
// don't let the area's own fitBounds override it once data loads.
let hasFitBoundsOnce = hasExplicitView;

// Thinner/lighter for the comfortable classes, progressively bolder for
// the demanding ones - same zoom range as before, per-class endpoints
// via a match expression nested inside the interpolation stops.
const LTS_LINE_WIDTH = [
  "interpolate", ["linear"], ["zoom"],
  12, ["match", ["to-string", ["get", "lts"]], "1", 1.0, "2", 1.2, "3", 1.8, "4", 2.2, 1.5],
  18, ["match", ["to-string", ["get", "lts"]], "1", 3.5, "2", 4.0, "3", 5.5, "4", 6.5, 5.0],
];
const GAP_EDGE_WIDTH = 4;

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
  if (!map.getSource("lts")) {
    map.addSource("lts", { type: "vector", url: pmtilesUrl });
  }
  if (!map.getLayer("lts-lines")) {
    map.addLayer({
      id: "lts-lines",
      type: "line",
      source: "lts",
      "source-layer": "lts",
      // Miter is MapLibre's default line-join: at low zoom, where many
      // short OSM road segments render just a few px apart, every heading
      // change between them shows up as a sharp point instead of a smooth
      // bend - reported as streets looking "too angular" at z11+. Round
      // joins/caps trace the same underlying geometry, just without the
      // spikes at each vertex.
      layout: { "line-join": "round", "line-cap": "round" },
      paint: {
        "line-color": LTS_COLOR_EXPRESSION,
        "line-width": LTS_LINE_WIDTH,
      },
    });
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
      filter: [
        "all",
        ["==", ["to-string", ["get", "is_gap_edge"]], "true"],
        ["!=", ["to-string", ["get", "has_parallel_cycleway"]], "true"],
      ],
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
}

map.on("style.load", addDataLayers);

// Bound once, not inside addDataLayers: maplibre resolves "lts-lines" at
// event time against whatever layers currently exist, so these keep
// working across setStyle() re-adding the layer with the same id.
// Below MIN_CLICK_ZOOM, streets are too close together to click reliably
// - "mousemove" (not "mouseenter") re-checks the zoom on every move so the
// cursor updates correctly even if the user scroll-zooms without moving
// the mouse off the street they're hovering.
map.on("mousemove", "lts-lines", () => {
  map.getCanvas().style.cursor = map.getZoom() >= MIN_CLICK_ZOOM ? "pointer" : "";
});
map.on("mouseleave", "lts-lines", () => { map.getCanvas().style.cursor = ""; });
map.on("click", "lts-lines", (e) => {
  if (map.getZoom() < MIN_CLICK_ZOOM) return;
  new maplibregl.Popup({ maxWidth: "280px" })
    .setLngLat(e.lngLat)
    .setHTML(popupHtml(e.features[0].properties))
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
// FAQ, Privacy) - purely informational, so intentionally NOT part of the
// URL-persisted view state (see syncUrlState below), unlike terrain/gap/
// basemap. Returns setOpen so callers that need to switch between two
// panels (the About->FAQ link right below) can drive both from outside.
function setupInfoPanel(toggleId, panelId, closeId) {
  const toggle = document.getElementById(toggleId);
  const panel = document.getElementById(panelId);
  function setOpen(open) {
    panel.classList.toggle("hidden", !open);
    toggle.classList.toggle("active", open);
  }
  toggle.addEventListener("click", () => setOpen(panel.classList.contains("hidden")));
  if (closeId) document.getElementById(closeId).addEventListener("click", () => setOpen(false));
  return setOpen;
}
const setAboutOpen = setupInfoPanel("about-toggle", "about-panel", "about-close");
const setFaqOpen = setupInfoPanel("faq-toggle", "faq-panel", "faq-close");
setupInfoPanel("privacy-toggle", "privacy-panel", "privacy-close");

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
  if (!map.getLayer("gap-edges")) return [];
  const unique = dedupeFeatures(map.queryRenderedFeatures({ layers: ["gap-edges"] }));

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
  if (map.getLayer("gap-edges")) {
    map.setLayoutProperty("gap-edges", "visibility", on ? "visible" : "none");
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
function syncUrlState() {
  const url = new URL(window.location.href);
  const center = map.getCenter();
  url.searchParams.set("area", area);
  url.searchParams.set("zoom", map.getZoom().toFixed(2));
  url.searchParams.set("lat", center.lat.toFixed(5));
  url.searchParams.set("lon", center.lng.toFixed(5));
  url.searchParams.set("pitch", map.getPitch().toFixed(0));
  url.searchParams.set("bearing", map.getBearing().toFixed(0));
  url.searchParams.set("bg", currentBasemap);
  url.searchParams.set("lts", [...activeLts].sort().join(","));
  url.searchParams.set("terrain", terrainOn ? "1" : "0");
  url.searchParams.set("gap", gapModeOn ? "1" : "0");
  url.searchParams.set("lang", currentLang);
  history.replaceState(null, "", url);
}

map.on("moveend", syncUrlState);
// moveend fires as soon as panning stops, but queryRenderedFeatures only
// sees tiles already loaded - a big pan into unloaded territory needs
// "idle" (fires once rendering has fully settled) too, or the list would
// silently under-report with no further update once tiles arrive.
map.on("moveend", () => { if (gapModeOn) renderGapInterventions(); });
map.on("idle", () => { if (gapModeOn) renderGapInterventions(); });
syncUrlState();
