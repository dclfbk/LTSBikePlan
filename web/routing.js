// Client-side LTS-preferring bike routing. Loads on demand only the
// per-comune routing graphs (web/data/<slug>_routing.bin, see
// scripts/build_routing_graph.py and decodeRoutingGraphBinary below)
// touched by a given start/end pair,
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
//
// No entry for LTS 0 ("Non ciclabile" - not merely stressful, no bike
// access at all) is deliberate: scripts/build_routing_graph.py already
// drops those edges entirely before they ever reach a routing.json file,
// so this should never actually see lts=0 - the `?? LTS_PENALTY[4]`
// fallback below is only a defensive last resort, not a real routing
// choice (see the Python module's own comment for the bug this used to be
// when 0 silently fell back to the LTS-4 rate here too).
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

// Decodes the compact binary wire format
// scripts/build_routing_graph.py's encode_routing_graph_binary writes to
// <slug>_routing.bin - see that Python function's own comment for the
// full layout rationale (single-producer/single-consumer format, so a
// hand-packed structure-of-arrays layout gets FlatBuffers' real benefit -
// zero-copy typed-array reads, no JSON.parse of a huge array-of-arrays -
// without a schema compiler or generated code).
//
// Layout (all little-endian), field order load-bearing - every
// multi-byte field before the two 1-byte ones, so each section starts at
// a naturally correct alignment with NO padding needed anywhere in the
// body, only once right after the header:
//   [u32] headerLen=H, [H bytes] UTF-8 JSON {slug,names,nodeCount,edgeCount}
//   [pad to next 8-byte boundary]
//   [f32 x NC] node lon, [f32 x NC] node lat, [f64 x NC] node OSM id
//   [u32 x EC] edge u_idx, [u32 x EC] edge v_idx, [f32 x EC] edge length_m,
//   [i32 x EC] edge name_idx, [u8 x EC] edge lts, [u8 x EC] edge facility_code
function decodeRoutingGraphBinary(buffer) {
  const view = new DataView(buffer);
  const headerLen = view.getUint32(0, true);
  const headerJson = new TextDecoder("utf-8").decode(new Uint8Array(buffer, 4, headerLen));
  const header = JSON.parse(headerJson);
  const nodeCount = header.nodeCount;
  const edgeCount = header.edgeCount;

  let offset = 4 + headerLen;
  offset += (8 - (offset % 8)) % 8; // same padding rule as the Python encoder

  const nodeLons = new Float32Array(buffer, offset, nodeCount); offset += nodeCount * 4;
  const nodeLats = new Float32Array(buffer, offset, nodeCount); offset += nodeCount * 4;
  const nodeOsmIds = new Float64Array(buffer, offset, nodeCount); offset += nodeCount * 8;
  const edgeU = new Uint32Array(buffer, offset, edgeCount); offset += edgeCount * 4;
  const edgeV = new Uint32Array(buffer, offset, edgeCount); offset += edgeCount * 4;
  const edgeLength = new Float32Array(buffer, offset, edgeCount); offset += edgeCount * 4;
  const edgeNameIdx = new Int32Array(buffer, offset, edgeCount); offset += edgeCount * 4;
  const edgeLts = new Uint8Array(buffer, offset, edgeCount); offset += edgeCount;
  const edgeFacility = new Uint8Array(buffer, offset, edgeCount); offset += edgeCount;

  return {
    slug: header.slug,
    names: header.names,
    nodeCount, edgeCount,
    nodeLons, nodeLats, nodeOsmIds,
    edgeU, edgeV, edgeLength, edgeNameIdx, edgeLts, edgeFacility,
  };
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

// Builds one in-memory graph from an array of decodeRoutingGraphBinary()
// results. Node identity is the edge's real OSM node id (see
// scripts/build_routing_graph.py's docstring) - the same OSM node shared
// by two adjacent comuni's independent extracts joins automatically, no
// coordinate-tolerance snapping needed. multigraph:true keeps parallel
// edges (e.g. a divided carriageway) as distinct links instead of one
// silently overwriting another (ngraph.graph's default).
function mergeRoutingGraphs(routingFiles) {
  const graph = createGraph({ multigraph: true });
  const coordByOsmId = new Map();

  for (const file of routingFiles) {
    const { nodeCount, edgeCount, nodeLons, nodeLats, nodeOsmIds, edgeU, edgeV, edgeLength, edgeNameIdx, edgeLts, edgeFacility, names, slug } = file;
    for (let i = 0; i < nodeCount; i++) {
      const osmId = nodeOsmIds[i];
      const coord = [nodeLons[i], nodeLats[i]];
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
    for (let i = 0; i < edgeCount; i++) {
      // nameIdx is only meaningful within this file's own `names` array -
      // resolve to the actual string now, before it's merged with other
      // files' edges (a shared/global index would be meaningless once
      // multiple files' name tables are mixed together).
      const nameIdx = edgeNameIdx[i];
      const name = nameIdx >= 0 ? names[nameIdx] : null;
      graph.addLink(
        nodeOsmIds[edgeU[i]], nodeOsmIds[edgeV[i]],
        { lts: edgeLts[i], lengthM: edgeLength[i], facilityCode: edgeFacility[i], name, comuneSlug: slug },
      );
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

// Among every node REACHABLE from `fromId` (a plain BFS over the merged
// graph - cheap even at a Trento-sized graph, and this only ever runs
// once findRoute's direct A* has already failed), returns whichever one
// sits closest (straight-line) to `targetLngLat`. Used when the actual
// destination isn't reachable at all - typically because the only
// physical connection onward is a non-cyclable road (LTS 0 edges are
// excluded from the graph entirely, see build_routing_graph.py's own
// comment on why) - so the router can still show how far a rider CAN get
// on cyclable roads, instead of a flat "no route".
function _nearestReachableNode(graph, fromId, targetLngLat, coordByOsmId) {
  const target = [targetLngLat.lng, targetLngLat.lat];
  const visited = new Set([fromId]);
  const queue = [fromId];
  let bestId = fromId;
  let bestDist = approxMetersBetween(coordByOsmId.get(fromId), target);
  let head = 0;
  while (head < queue.length) {
    const current = queue[head++];
    const links = graph.getLinks(current);
    if (!links) continue;
    links.forEach((link) => {
      const other = link.fromId === current ? link.toId : link.fromId;
      if (visited.has(other)) return;
      visited.add(other);
      queue.push(other);
      const coord = coordByOsmId.get(other);
      if (!coord) return;
      const dist = approxMetersBetween(coord, target);
      if (dist < bestDist) {
        bestDist = dist;
        bestId = other;
      }
    });
  }
  return bestId;
}

// Shared by both the direct and partial-fallback cases below: turns a
// list of ngraph path NODES (start -> end order already) into the
// { feature, segments } shape findRoute returns. pathFinder.find() only
// hands back the node sequence - the {lts, name, ...} data lives on the
// LINKS between them, recovered per consecutive pair via
// _bestLinkBetween (same "cheapest wins" rule A* implicitly used).
function _buildRouteResult(pathNodes, mergedGraph, partial) {
  const coordinates = pathNodes.map((node) => node.data);
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
    partial,
  };
}

// Runs A* over the merged graph, preferring low-LTS edges via edgeCost.
// Returns { feature, segments, partial } where `feature` is a GeoJSON
// LineString and `segments` is one entry per original graph edge along
// the path (segments[i] describes the edge between
// feature.geometry.coordinates[i] and [i+1]): { lts, lengthM,
// facilityCode, name, comuneSlug }.
//
// If the actual destination isn't reachable at all from the start
// (typically: the only physical way onward is a non-cyclable road - LTS 0
// edges are excluded from the graph entirely, see
// build_routing_graph.py), falls back to routing as far as the closest
// point ON THE CYCLABLE NETWORK gets to the destination
// (_nearestReachableNode) rather than failing outright - `partial: true`
// marks this case so callers can tell a rider "this is as far as you can
// get by bike" instead of silently presenting it as the real route.
//
// Returns null (not { feature: null, ... }) only when there is truly
// nothing to show - start and end snap to the same node, or start itself
// has no reachable neighbours at all - the definitive "no route" signal.
function findRoute(startLngLat, endLngLat, mergedGraph, coordByOsmId) {
  const startId = _nearestNode(startLngLat, coordByOsmId);
  const endId = _nearestNode(endLngLat, coordByOsmId);
  if (startId === null || endId === null || startId === endId) return null;

  const pathFinder = ngraphPath.aStar(mergedGraph, {
    heuristic: (fromNode, toNode) => approxMetersBetween(fromNode.data, toNode.data) * _MIN_PENALTY,
    distance: (fromNode, toNode, link) => edgeCost(link.data.lts, link.data.lengthM),
  });

  const found = pathFinder.find(startId, endId);
  if (found && found.length >= 2) {
    // ngraph.path returns the path from `toId` back to `fromId` - reverse
    // to get start -> end order for drawing.
    return _buildRouteResult(found.reverse(), mergedGraph, false);
  }

  const nearestId = _nearestReachableNode(mergedGraph, startId, endLngLat, coordByOsmId);
  if (nearestId === startId) return null; // start itself is isolated - nothing reachable to show

  const partialFound = pathFinder.find(startId, nearestId);
  if (!partialFound || partialFound.length < 2) return null;
  return _buildRouteResult(partialFound.reverse(), mergedGraph, true);
}
