// Client-side LTS-preferring bike routing. Loads on demand only the
// per-comune routing graphs (web/data/<slug>_routing.json, see
// scripts/build_routing_graph.py) touched by a given start/end pair,
// stitches them into one in-memory graph, and runs ngraph.path's A* with
// an LTS-weighted cost - no routing server. See web/app.js's
// RoutingControl for the UI that drives these functions.
//
// Loaded before app.js (plain global scope, same convention as i18n.js -
// no ES modules anywhere in this app). Depends on the ngraph.graph/
// ngraph.path <script> tags in index.html (globals: createGraph,
// ngraphPath).

// Mirrors code/ltsbikeplan/domain/routing_cost.py's LTS_PENALTY exactly -
// no shared build step between the Python pipeline and this static site,
// so if that table changes there, update this one too.
const LTS_PENALTY = { 1: 1.0, 2: 1.3, 3: 2.5, 4: 6.0 };

function edgeCost(lts, lengthM) {
  return lengthM * (LTS_PENALTY[lts] ?? LTS_PENALTY[4]);
}

// The lowest possible penalty in the table (LTS 1) - scaling the
// straight-line heuristic by this keeps A* admissible (it can never
// overestimate the true remaining cost, since no real route is shorter
// than a straight line, and no edge is ever cheaper per meter than the
// lowest LTS class).
const _MIN_PENALTY = Math.min(...Object.values(LTS_PENALTY));

// Flat-earth approximation - fine at comune/adjacent-comune scale (a few
// km at most), not meant for long-haul geodesy.
function approxMetersBetween(a, b) {
  const latRad = (a[1] * Math.PI) / 180;
  const dx = (b[0] - a[0]) * 111320 * Math.cos(latRad);
  const dy = (b[1] - a[1]) * 110540;
  return Math.sqrt(dx * dx + dy * dy);
}

// Filters comuniIndex (web/data/comuni_index.json, loaded client-side by
// web/app.js) to entries with routing coverage whose bbox intersects the
// start/end rectangle expanded by marginDeg on every side. Callable again
// with a larger marginDeg to widen the search after a failed findRoute()
// - see RoutingControl's retry loop in web/app.js.
function candidateComuniForRoute(startLngLat, endLngLat, comuniIndex, marginDeg) {
  const minLng = Math.min(startLngLat.lng, endLngLat.lng) - marginDeg;
  const maxLng = Math.max(startLngLat.lng, endLngLat.lng) + marginDeg;
  const minLat = Math.min(startLngLat.lat, endLngLat.lat) - marginDeg;
  const maxLat = Math.max(startLngLat.lat, endLngLat.lat) + marginDeg;

  const slugs = new Set();
  for (const entry of comuniIndex || []) {
    if (!entry.has_routing) continue;
    const [ex0, ey0, ex1, ey1] = entry.bbox;
    const intersects = ex0 <= maxLng && ex1 >= minLng && ey0 <= maxLat && ey1 >= minLat;
    if (intersects) slugs.add(entry.slug);
  }
  return slugs;
}

// Builds one in-memory graph from an array of parsed <slug>_routing.json
// objects. Node identity is the edge's real OSM node id (see
// scripts/build_routing_graph.py's docstring) - the same OSM node shared
// by two adjacent comuni's independent extracts joins automatically, no
// coordinate-tolerance snapping needed. multigraph:true keeps parallel
// edges (e.g. a divided carriageway) as distinct links instead of one
// silently overwriting another (ngraph.graph's default).
function mergeRoutingGraphs(routingFiles) {
  const graph = createGraph({ multigraph: true });
  const coordByOsmId = new Map();

  for (const file of routingFiles) {
    const { nodes, node_osm_ids, edges, names, slug } = file;
    for (let i = 0; i < node_osm_ids.length; i++) {
      const osmId = node_osm_ids[i];
      const coord = nodes[i];
      const existing = coordByOsmId.get(osmId);
      if (existing) {
        // Defensive only - expected to never actually fire, since two
        // adjacent comuni's extracts should compute an identical
        // coordinate for the same shared OSM node. A real mismatch here
        // would mean the two files were built from OSM data that changed
        // between their two fetch times.
        if (approxMetersBetween(existing, coord) > 5) {
          console.warn(`routing.js: node ${osmId} coordinate differs by >5m across comuni files - keeping the first value seen.`);
        }
        continue;
      }
      coordByOsmId.set(osmId, coord);
      graph.addNode(osmId, coord);
    }
    for (const [uIdx, vIdx, lts, lengthM, facilityCode, nameIdx] of edges) {
      // nameIdx is only meaningful within this file's own `names` array -
      // resolve to the actual string now, before it's merged with other
      // files' edges (a shared/global index would be meaningless once
      // multiple files' name tables are mixed together).
      const name = nameIdx >= 0 ? names[nameIdx] : null;
      graph.addLink(node_osm_ids[uIdx], node_osm_ids[vIdx], { lts, lengthM, facilityCode, name, comuneSlug: slug });
    }
  }
  return { graph, coordByOsmId };
}

// Among every link connecting the two nodes (checked both directions -
// the graph is undirected in intent even though ngraph stores links
// directionally), returns the one A* would have implicitly preferred: the
// cheapest by edgeCost. Matches build_routing_graph.py's own documented
// "cheapest wins" tie-break for parallel edges (e.g. a divided
// carriageway) - used to recover which link's {lts, name, ...} a found
// path segment actually corresponds to, since ngraph.path's result is a
// list of NODES, not the links between them.
function _bestLinkBetween(graph, fromId, toId) {
  let best = null;
  let bestCost = Infinity;
  const consider = (link) => {
    const cost = edgeCost(link.data.lts, link.data.lengthM);
    if (cost < bestCost) {
      bestCost = cost;
      best = link;
    }
  };
  (graph.getLinks(fromId) || []).forEach((link) => {
    if (link.fromId === fromId && link.toId === toId) consider(link);
    if (link.fromId === toId && link.toId === fromId) consider(link);
  });
  return best;
}

// Nearest OSM node id to a click point - linear scan, fine at the node
// counts a handful of merged comuni produce (no spatial index needed).
function _nearestNode(lngLat, coordByOsmId) {
  let bestId = null;
  let bestDist = Infinity;
  for (const [osmId, coord] of coordByOsmId) {
    const dist = approxMetersBetween([lngLat.lng, lngLat.lat], coord);
    if (dist < bestDist) {
      bestDist = dist;
      bestId = osmId;
    }
  }
  return bestId;
}

// Runs A* over the merged graph, preferring low-LTS edges via edgeCost.
// Returns { feature, segments } where `feature` is a GeoJSON LineString
// and `segments` is one entry per original graph edge along the path
// (segments[i] describes the edge between feature.geometry.coordinates[i]
// and [i+1]): { lts, lengthM, facilityCode, name, comuneSlug }. Returns
// null (not { feature: null, ... }) if no route exists (start and end
// snap to the same node, or the graph is disconnected between them) -
// callers treat null as the definitive "no route" signal, never a
// partial/wrong path.
function findRoute(startLngLat, endLngLat, mergedGraph, coordByOsmId) {
  const startId = _nearestNode(startLngLat, coordByOsmId);
  const endId = _nearestNode(endLngLat, coordByOsmId);
  if (startId === null || endId === null || startId === endId) return null;

  const pathFinder = ngraphPath.aStar(mergedGraph, {
    heuristic: (fromNode, toNode) => approxMetersBetween(fromNode.data, toNode.data) * _MIN_PENALTY,
    distance: (fromNode, toNode, link) => edgeCost(link.data.lts, link.data.lengthM),
  });

  const found = pathFinder.find(startId, endId);
  if (!found || found.length < 2) return null;

  // ngraph.path returns the path from `toId` back to `fromId` - reverse
  // to get start -> end order for drawing.
  const pathNodes = found.reverse();
  const coordinates = pathNodes.map((node) => node.data);

  // pathFinder.find() only returns the sequence of NODES - the {lts,
  // name, ...} data lives on the LINKS between them, which the search
  // itself doesn't hand back. Recover it per consecutive pair via
  // _bestLinkBetween (same "cheapest wins" rule A* implicitly used).
  const segments = [];
  for (let i = 0; i < pathNodes.length - 1; i++) {
    const link = _bestLinkBetween(mergedGraph, pathNodes[i].id, pathNodes[i + 1].id);
    segments.push(
      link
        ? { lts: link.data.lts, lengthM: link.data.lengthM, facilityCode: link.data.facilityCode, name: link.data.name, comuneSlug: link.data.comuneSlug }
        : { lts: 4, lengthM: approxMetersBetween(coordinates[i], coordinates[i + 1]), facilityCode: 0, name: null, comuneSlug: null },
    );
  }

  return {
    feature: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates } },
    segments,
  };
}
