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
//
// The gaps between classes (previously 1.0/1.3/2.5/6.0) were narrowed
// after a real-world mismatch, validated on two independent real routes
// against Valhalla's/OSRM's actual bicycle routing - see
// domain/routing_cost.py's own LTS_PENALTY comment for the full story.
// Narrowing this AND raising FATIGUE_PENALTY below together was what
// actually matched real routers' choices; neither alone was enough.
const LTS_PENALTY = { 1: 1.0, 2: 1.2, 3: 1.6, 4: 3.0 };

// Mirrors domain/routing_cost.py's FATIGUE_PENALTY exactly - see that
// table's own comment for why this is a SEPARATE multiplier from
// LTS_PENALTY (stress vs physical effort are different axes; without
// this, two same-LTS streets - one flat, one with a long climb too mild
// to bump the LTS class - cost identically) and why it's symmetric
// (unsigned slope magnitude, can't tell uphill from downhill). Indexed by
// scripts/build_routing_graph.py's slope_class_code (0=flat..5=impossible);
// code 255 (UNKNOWN_SLOPE_CLASS_CODE, no reliable reading) never indexes
// into this array, see edgeCost below. Raised alongside LTS_PENALTY's own
// narrowing above (previously 1.0/1.05/1.2/1.5/2.0/2.0), then raised
// again on just the top two tiers (previously 4.0/4.0, one shared
// ceiling) after a real Trento -> Pergine Valsugana route kept crossing
// Passo Cimirlo despite that ceiling - see domain/routing_cost.py's own
// FATIGUE_PENALTY comment for the full validation (client-side findRoute
// re-run confirming the switch to a real alternative, the Ponte Alto
// valley road, plus an ordinary flat-route check that this doesn't
// perturb routing where slope doesn't matter).
const FATIGUE_PENALTY = [1.0, 1.1, 2.0, 4.0, 8.0, 16.0];
const UNKNOWN_SLOPE_CLASS_CODE = 255;

// NOTE - deliberately does NOT gate this on edge length (an earlier
// version required lengthM >= 500, mirroring lts_rules.py's own DEM-noise
// threshold for its LTS-class bump). That was wrong here: checked against
// a real steep road (Trento's Passo Cimirlo, ~500 edges), EVERY edge was
// under 500m (median ~11m - mountain roads get chopped into many short
// segments per curve), so the length gate silently zeroed out the fatigue
// penalty for the entire climb. See domain/routing_cost.py's edge_cost
// for the full reasoning on why a length gate is the wrong call for a
// continuous, length-scaled cost (unlike lts_rules.py's discrete class
// bump) - a wrongly-classified short edge can only ever miscount total
// path cost by a few meters, self-limiting in a way a class jump isn't.

// Mirrors domain/routing_cost.py's STRESS_RUN_PENALTY exactly - see that
// table's own comment for the full reasoning (a third, independent axis:
// how LONG a continuously-stressful named street is, not just how
// stressful or how tiring). Indexed by scripts/build_routing_graph.py's
// stress_run_code (0 = under 200m ... 4 = over 3000m). Only applied when
// lts >= 2 - a long QUIET street is the whole point of this router, not
// something to penalize.
const STRESS_RUN_PENALTY = [1.0, 1.0, 1.15, 1.35, 1.6];

// Mirrors domain/routing_cost.py's SURFACE_FATIGUE_PENALTY exactly - a
// fourth, independent axis: surface roughness is physical effort, not
// traffic stress, same reasoning as FATIGUE_PENALTY above. Indexed by
// scripts/build_routing_graph.py's surface_class_code (0=none/paved,
// 1=moderate, 2=severe).
const SURFACE_FATIGUE_PENALTY = [1.0, 1.3, 1.8];

// `profile` (optional) overrides which LTS_PENALTY table applies, or
// bypasses all four multipliers entirely - see ROUTE_PROFILES below and
// RoutingControl's "3 alternative routes" opt-in feature (web/app.js).
// Omitted, edgeCost is exactly the production single-route cost this
// module always used before that feature existed - every existing call
// site (findRoute's own default, _totalRouteCost's widen-retry
// comparison) keeps behaving identically.
function edgeCost(lts, lengthM, slopeClassCode, stressRunCode, surfaceClassCode, profile) {
  if (profile && profile.shortest) return lengthM; // "direct" variant: pure distance, ignores LTS/fatigue/stress/surface entirely
  const ltsTable = (profile && profile.ltsPenalty) || LTS_PENALTY;
  const ltsMultiplier = ltsTable[lts] ?? ltsTable[4];
  const fatigueMultiplier =
    slopeClassCode !== undefined && slopeClassCode !== UNKNOWN_SLOPE_CLASS_CODE
      ? FATIGUE_PENALTY[slopeClassCode] ?? 1.0
      : 1.0;
  const stressRunMultiplier =
    stressRunCode !== undefined && lts >= 2 ? STRESS_RUN_PENALTY[stressRunCode] ?? 1.0 : 1.0;
  const surfaceFatigueMultiplier =
    surfaceClassCode !== undefined ? SURFACE_FATIGUE_PENALTY[surfaceClassCode] ?? 1.0 : 1.0;
  return lengthM * ltsMultiplier * fatigueMultiplier * stressRunMultiplier * surfaceFatigueMultiplier;
}

// The lowest possible penalty in the table (LTS 1) - scaling the
// straight-line heuristic by this keeps A* admissible (it can never
// overestimate the true remaining cost, since no real route is shorter
// than a straight line, and no edge is ever cheaper per meter than the
// lowest LTS class). FATIGUE_PENALTY, STRESS_RUN_PENALTY and
// SURFACE_FATIGUE_PENALTY entries are all >= 1.0 (each only ever makes an
// edge MORE expensive, never cheaper), so this bound stays valid without
// folding any of them into it too.
const _MIN_PENALTY = Math.min(...Object.values(LTS_PENALTY));

// Minimum possible per-meter cost under a given profile - same
// admissibility reasoning as _MIN_PENALTY above, generalized so findRoute's
// A* heuristic stays valid for every profile below, not just the default.
function _minPenaltyForProfile(profile) {
  if (profile && profile.shortest) return 1.0;
  const ltsTable = (profile && profile.ltsPenalty) || LTS_PENALTY;
  return Math.min(...Object.values(ltsTable));
}

// The three cost-function variants behind RoutingControl's opt-in
// "Mostra percorsi alternativi" checkbox (web/app.js) - approved design,
// see three_routes_mockup_v2 in this session's scratchpad. Only
// LTS_PENALTY (and, for "direct", every multiplier) differs between
// variants; FATIGUE_PENALTY/STRESS_RUN_PENALTY/SURFACE_FATIGUE_PENALTY
// stay the production values for all three - varying just the traffic-
// stress axis (and, for "direct", dropping stress entirely) is what
// produces meaningfully different real routes without re-litigating the
// fatigue tuning validated separately (see FATIGUE_PENALTY's own comment).
//
// "lowStress" has no override (undefined profile = production edgeCost,
// see that function's own comment) - kept here anyway so callers can
// address all three uniformly by name.
const ROUTE_PROFILES = {
  lowStress: undefined,
  // Softened LTS gaps (was 1.0/1.2/1.6/3.0) - narrowed the same way
  // LTS_PENALTY itself was narrowed once already (see that table's own
  // comment), just further, so a moderately-busy street stops being
  // avoided at nearly any distance cost the way "lowStress" deliberately
  // does.
  balanced: { ltsPenalty: { 1: 1.0, 2: 1.1, 3: 1.3, 4: 1.8 } },
  // Pure shortest-path: edgeCost above returns lengthM alone, so this is
  // exactly what Valhalla/OSRM's plain "bicycle, fastest" profile would
  // find on the same graph - the natural "what if it just ignored stress"
  // comparison point for the other two.
  direct: { shortest: true },
};

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
//   [i32 x EC] edge name_idx, [u8 x EC] edge lts, [u8 x EC] edge facility_code,
//   [u8 x EC] edge slope_class_code (255 = unknown, see edgeCost),
//   [u8 x EC] edge is_pedestrian (1 = OSM highway=pedestrian, see estimateRouteTimeMinutes),
//   [u8 x EC] edge stress_run_code (bucketed named-street run length, see edgeCost),
//   [u8 x EC] edge surface_class_code (0=none, 1=moderate, 2=severe, see edgeCost)
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
  // A .bin built by a build_routing_graph.py from before this field
  // existed is edgeCount bytes SHORTER than a current one expects here -
  // scripts/build_italy_map_comuni_cron.sh regenerates one comune at a
  // time, so an old file can still be served well after this code ships.
  // Falling back to an all-UNKNOWN_SLOPE_CLASS_CODE array (rather than
  // letting the out-of-bounds Uint8Array construction throw) keeps such a
  // comune routable in the meantime - same "soft preference, degrades
  // gracefully" spirit as the rest of this module - at the cost of no
  // fatigue penalty for it until its own regeneration lands.
  const hasSlopeClass = buffer.byteLength - offset >= edgeCount;
  const edgeSlopeClass = hasSlopeClass
    ? new Uint8Array(buffer, offset, edgeCount)
    : new Uint8Array(edgeCount).fill(UNKNOWN_SLOPE_CLASS_CODE);
  if (hasSlopeClass) offset += edgeCount;

  // Same old-file tolerance as edgeSlopeClass above, one field younger -
  // a .bin from before is_pedestrian existed is missing this trailing
  // array too. Falling back to all-zero (not pedestrian) rather than
  // throwing keeps such a comune routable with just no pedestrian-speed
  // cap applied yet, not a broken decode.
  const hasIsPedestrian = buffer.byteLength - offset >= edgeCount;
  const edgeIsPedestrian = hasIsPedestrian
    ? new Uint8Array(buffer, offset, edgeCount)
    : new Uint8Array(edgeCount); // defaults to all zeros
  if (hasIsPedestrian) offset += edgeCount;

  // Same old-file tolerance again, one field younger still - falls back
  // to code 0 (the shortest bucket, i.e. no stress-run penalty) rather
  // than throwing.
  const hasStressRun = buffer.byteLength - offset >= edgeCount;
  const edgeStressRun = hasStressRun
    ? new Uint8Array(buffer, offset, edgeCount)
    : new Uint8Array(edgeCount); // defaults to all zeros (bucket 0)
  if (hasStressRun) offset += edgeCount;

  // Same old-file tolerance again, one field younger still - falls back
  // to code 0 (no surface penalty) rather than throwing.
  const hasSurfaceClass = buffer.byteLength - offset >= edgeCount;
  const edgeSurfaceClass = hasSurfaceClass
    ? new Uint8Array(buffer, offset, edgeCount)
    : new Uint8Array(edgeCount); // defaults to all zeros (code 0, no penalty)
  if (hasSurfaceClass) offset += edgeCount;

  return {
    slug: header.slug,
    names: header.names,
    nodeCount, edgeCount,
    nodeLons, nodeLats, nodeOsmIds,
    edgeU, edgeV, edgeLength, edgeNameIdx, edgeLts, edgeFacility, edgeSlopeClass, edgeIsPedestrian, edgeStressRun,
    edgeSurfaceClass,
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
    const { nodeCount, edgeCount, nodeLons, nodeLats, nodeOsmIds, edgeU, edgeV, edgeLength, edgeNameIdx, edgeLts, edgeFacility, edgeSlopeClass, edgeIsPedestrian, edgeStressRun, edgeSurfaceClass, names, slug } = file;
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
        { lts: edgeLts[i], lengthM: edgeLength[i], facilityCode: edgeFacility[i], slopeClass: edgeSlopeClass[i], isPedestrian: edgeIsPedestrian[i], stressRunCode: edgeStressRun[i], surfaceClass: edgeSurfaceClass[i], name, comuneSlug: slug },
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
function _bestLinkBetween(graph, fromId, toId, profile) {
  let best = null;
  let bestCost = Infinity;
  const consider = (link) => {
    const cost = edgeCost(link.data.lts, link.data.lengthM, link.data.slopeClass, link.data.stressRunCode, link.data.surfaceClass, profile);
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
function _buildRouteResult(pathNodes, mergedGraph, partial, profile) {
  const coordinates = pathNodes.map((node) => node.data);
  const segments = [];
  for (let i = 0; i < pathNodes.length - 1; i++) {
    const link = _bestLinkBetween(mergedGraph, pathNodes[i].id, pathNodes[i + 1].id, profile);
    segments.push(
      link
        ? {
            lts: link.data.lts,
            lengthM: link.data.lengthM,
            facilityCode: link.data.facilityCode,
            isPedestrian: link.data.isPedestrian,
            // slopeClass/stressRunCode/surfaceClass aren't shown anywhere
            // in the UI - carried through only so web/app.js's own
            // widen-and-retry (_findRoute) can recompute this route's
            // real total edgeCost to compare against a wider margin's
            // result, the same way A* itself weighed each edge.
            slopeClass: link.data.slopeClass,
            stressRunCode: link.data.stressRunCode,
            surfaceClass: link.data.surfaceClass,
            name: link.data.name,
            comuneSlug: link.data.comuneSlug,
          }
        : {
            lts: 4,
            lengthM: approxMetersBetween(coordinates[i], coordinates[i + 1]),
            facilityCode: 0,
            isPedestrian: 0,
            slopeClass: undefined,
            stressRunCode: undefined,
            surfaceClass: undefined,
            name: null,
            comuneSlug: null,
          },
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
// `profile` (optional, one of ROUTE_PROFILES' values) selects which cost
// function A* minimizes - omitted, this is exactly the production
// low-stress search every existing call site already relies on. Used by
// RoutingControl to compute the "balanced"/"direct" alternative routes
// against the SAME merged graph the default search already fetched, no
// extra network I/O.
function findRoute(startLngLat, endLngLat, mergedGraph, coordByOsmId, profile) {
  const startId = _nearestNode(startLngLat, coordByOsmId);
  const endId = _nearestNode(endLngLat, coordByOsmId);
  if (startId === null || endId === null || startId === endId) return null;

  const minPenalty = _minPenaltyForProfile(profile);
  const pathFinder = ngraphPath.aStar(mergedGraph, {
    heuristic: (fromNode, toNode) => approxMetersBetween(fromNode.data, toNode.data) * minPenalty,
    distance: (fromNode, toNode, link) => edgeCost(link.data.lts, link.data.lengthM, link.data.slopeClass, link.data.stressRunCode, link.data.surfaceClass, profile),
  });

  const found = pathFinder.find(startId, endId);
  if (found && found.length >= 2) {
    // ngraph.path returns the path from `toId` back to `fromId` - reverse
    // to get start -> end order for drawing.
    return _buildRouteResult(found.reverse(), mergedGraph, false, profile);
  }

  const nearestId = _nearestReachableNode(mergedGraph, startId, endLngLat, coordByOsmId);
  if (nearestId === startId) return null; // start itself is isolated - nothing reachable to show

  const partialFound = pathFinder.find(startId, nearestId);
  if (!partialFound || partialFound.length < 2) return null;
  return _buildRouteResult(partialFound.reverse(), mergedGraph, true, profile);
}
