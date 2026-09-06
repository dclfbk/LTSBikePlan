// Service worker: two independent jobs, kept deliberately separate below.
//
// 1) App shell (this list) - cache-first, versioned. Bump SHELL_VERSION
//    whenever any of these files change (alongside app.js's own
//    APP_VERSION, though the two numbers don't have to match - this one
//    only tracks the shell, not app.js's own in-app "About" display) so
//    activate's cleanup below drops the old cache and every asset is
//    re-fetched fresh. Lets the whole UI (map controls, styles, vendor
//    libs) load instantly on a repeat visit, and still load (empty map,
//    but a working app) with no network at all.
//
// 2) Per-comune data (web/data/comuni_index.json, *_routing.bin) - NOT
//    precached (there are ~7900 comuni, no way to know which ones a given
//    visitor needs), instead cached opportunistically the first time each
//    is fetched, stale-while-revalidate: serve the cached copy instantly
//    if there is one (revisiting a comune you already routed through, or
//    the shared comuni_index.json), while a background fetch refreshes
//    the cache for next time - these files DO get rebuilt periodically
//    (see the incremental per-comune cron), so pure cache-forever would
//    eventually serve stale routing graphs.
//
// Deliberately NOT handled here: *_lts.pmtiles. pmtiles.js reads them via
// HTTP Range requests (see PMTiles' own FetchSource) - caching a Range
// response correctly means slicing a stored ArrayBuffer and reconstructing
// a 206 with matching Content-Range, which this file does not attempt.
// Rule 1 in the fetch handler below (skip any request carrying a Range
// header) opts all of that traffic out and lets it hit the network/the
// browser's own HTTP cache exactly as it did with no service worker at
// all - correctness over an offline map layer for now.

const SHELL_VERSION = "shell-v2";
const DATA_CACHE = "data-v1";

const SHELL_ASSETS = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "i18n.js",
  "routing.js",
  "manifest.json",
  "favicon.ico",
  "favicon.svg",
  "logo.svg",
  "assets/vendor/maplibre-gl-5.24.0.js",
  "assets/vendor/maplibre-gl-5.24.0.css",
  "assets/vendor/pmtiles-4.5.0.js",
  "assets/fonts/atkinson-hyperlegible-next-latin-wght-normal.woff2",
  "assets/icons/icon-192.png",
  "assets/icons/icon-512.png",
  "assets/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_VERSION)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key !== SHELL_VERSION && key !== DATA_CACHE)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

// web/data/comuni_index.json and web/data/<slug>_routing.bin - both
// plain whole-file GETs (unlike the pmtiles ranged reads excluded above).
function isCacheableDataRequest(url) {
  return url.pathname.endsWith("/data/comuni_index.json")
    || /\/data\/[^/]+_routing\.bin$/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only ever handle same-origin GETs - cross-origin (basemap style/tiles,
  // Nominatim, Mapterhorn DEM) and any non-GET pass straight through
  // untouched, same as with no service worker installed.
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // See the pmtiles note up top - a Range header means this is exactly
  // the kind of request this service worker does not attempt to cache.
  if (request.headers.has("range")) return;

  if (isCacheableDataRequest(url)) {
    event.respondWith(
      caches.open(DATA_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        const networkFetch = fetch(request)
          .then((response) => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          })
          .catch(() => null);
        // Cached copy wins the race when there is one - instant, and
        // correct often enough given how rarely one comune's own data
        // changes - while networkFetch still refreshes the cache in the
        // background for next time. Only actually wait on the network
        // when this is the first time this file's ever been requested.
        return cached || (await networkFetch) || Response.error();
      })
    );
    return;
  }

  // Everything left: same-origin, no Range header, not comuni_index.json/
  // *_routing.bin. Covers every precached SHELL_ASSETS entry (served
  // instantly from the install-time cache) and anything never precached
  // (faq.json, the /stats/ page's own files, a *_lts.pmtiles' rare
  // non-ranged request) - caches.match simply misses for those and
  // fetch() runs exactly as if this service worker didn't exist, so
  // there's no need to whitelist SHELL_ASSETS' paths again here.
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  );
});
