# Client-Side Bike Routing

Point-to-point bike routing inside the [web viewer](WEB.md), entirely client-side - no routing server, no external routing API. A rider picks a start/end point on the map and gets an LTS-preferring route computed in the browser via A*, using the same LTS/slope/surface data the pipeline already exports. This exists as its own doc (split out of [WEB.md](WEB.md)) because the design has a few load-bearing decisions worth keeping in one place rather than scattered across inline comments alone.

## Why client-side

A routing *server* would need the whole national graph loaded and connected at once. This viewer instead ships one small binary graph per comune (`web/data/<slug>_routing.bin`) and only loads, at request time, the handful actually needed for a given start/end pair - see "Loading strategy" below. That only works because of one property of the underlying data:

**Node identity is the edge's real, un-renumbered OSM node id.** osmnx/pyrosm never remap it anywhere in this project's ingestion path (no `truncate_graph_polygon`/`simplify_graph`/`consolidate_intersections` call exists - see `code/ltsbikeplan/services/osm_pbf_service.py`). Two independently-fetched adjacent comuni therefore share the same id for any OSM node that lies in both extracts, so the client can stitch a route across a comune boundary by matching ids directly - no coordinate-rounding/tolerance guesswork needed. Verified on a real adjacent-comune pair (Aglié/Bairo): shared OSM node ids matched to the exact same coordinate in both files.

## Data: `<slug>_routing.bin`

Built by `scripts/build_routing_graph.py <slug> [data_dir]`, from two of `compute-lts`'s own outputs: `<slug>_all_lts.parquet` (edges: length/lts/... - kept even after the sibling `.geojson` is deleted to reclaim disk, since routing needs it) and `<slug>_nodes.parquet` (real node positions: osmid/x/y). Node **coordinates** come from the nodes file, not inferred from edge geometry endpoints - an earlier version took that shortcut (an edge's LineString's first/last coordinate = u's/v's own position) and measured up to ~190m of misplacement on real data, because this project's edge geometry isn't guaranteed oriented u→v for every row (a two-way street's reverse-direction row can carry the same unflipped geometry as its forward counterpart). LTS 0 edges (not cyclable at all) are dropped entirely before export - a client that only ever sees cyclable edges doesn't need to filter them out again.

### Binary layout

A hand-packed structure-of-arrays format, not JSON - single producer (this script)/single consumer (`web/routing.js`), so this gets FlatBuffers' real benefit (zero-copy typed-array reads on the client, no `JSON.parse` of a huge array-of-arrays) without a schema compiler or generated code. All little-endian; field order is load-bearing - every multi-byte field comes before the 1-byte ones, so each section starts at a naturally correct alignment with no padding anywhere in the body, only once right after the header:

```
[u32] headerLen=H, [H bytes] UTF-8 JSON {slug, names, nodeCount, edgeCount}
[pad to next 8-byte boundary]
[f32 × NC] node lon
[f32 × NC] node lat
[f64 × NC] node OSM id
[u32 × EC] edge u_idx, [u32 × EC] edge v_idx        (indices into the node arrays above)
[f32 × EC] edge length_m
[i32 × EC] edge name_idx                             (index into header's `names`, -1 = unnamed)
[u8  × EC] edge lts                                  (1-4; 0 never appears, see above)
[u8  × EC] edge facility_code                        (0=street, 1=cycleway, 2=path - see facility_code())
[u8  × EC] edge slope_class_code                     (0=flat..5=impossible, 255=unknown - see slope_class_code())
[u8  × EC] edge is_pedestrian                        (1 = OSM highway=pedestrian)
[u8  × EC] edge stress_run_code                      (bucketed length of the continuously-stressful named street this edge belongs to)
[u8  × EC] edge surface_class_code                   (0=none/paved, 1=moderate, 2=severe)
```
Decoded client-side by `web/routing.js`'s `decodeRoutingGraphBinary()` - keep that function and this layout in sync if either changes.

## Cost function: four independent penalty axes

The router doesn't just minimize distance, and it doesn't collapse everything into one LTS number either - `edgeCost()` (duplicated deliberately in both `code/ltsbikeplan/domain/routing_cost.py`, for the batch pipeline, and `web/routing.js`, for the client - no shared build step between them, so a change to one table needs the same change in the other) multiplies length by four independent multipliers, each answering a different question:

| Axis | Table | Question it answers |
|---|---|---|
| `LTS_PENALTY` | `{1: 1.0, 2: 1.2, 3: 1.6, 4: 3.0}` | How stressful is this street? |
| `FATIGUE_PENALTY` | `[1.0, 1.1, 2.0, 4.0, 8.0, 16.0]`, indexed by slope class | How physically tiring is it (independent of stress - a flat busy street and a quiet steep climb are stressful/tiring for different reasons)? |
| `STRESS_RUN_PENALTY` | `[1.0, 1.0, 1.15, 1.35, 1.6]`, indexed by stress-run bucket, only applied when `lts >= 2` | How LONG is the continuously-stressful named street this edge belongs to (a third axis from plain per-edge LTS - a 3km busy corridor should cost more than a 3km road broken into short stressful segments by frequent quiet crossings, even at the same LTS)? |
| `SURFACE_FATIGUE_PENALTY` | `[1.0, 1.3, 1.8]`, indexed by surface class | How rough is the surface (physical effort again, independent of both stress and slope)? |

`LTS_PENALTY`'s gaps were narrowed from an earlier, wider set (1.0/1.3/2.5/6.0) after validating against Valhalla's/OSRM's actual bicycle routing on two independent real routes - narrowing this AND raising `FATIGUE_PENALTY` together is what actually matched real routers' choices; neither alone was enough (see `domain/routing_cost.py`'s own comment for the full story, including why the top two fatigue tiers were raised again on their own after a real Trento → Pergine Valsugana route kept crossing a mountain pass despite the first fix).

A* stays admissible because every multiplier is ≥ 1.0 (only ever makes an edge *more* expensive, never cheaper) - the straight-line heuristic is scaled by the single lowest possible penalty in the whole system (`LTS_PENALTY[1] = 1.0`), so it can never overestimate true remaining cost.

## Loading strategy

The client never loads more than it needs:

1. **`candidateComuniForRoute(start, end, comuniIndex, marginDeg)`** - a padded bounding-box check against `web/data/comuni_index.json`'s per-comune bbox (see [WEB.md](WEB.md)'s tileset section for how that index is built), filtered to entries with `has_routing: true`. Returns just the slugs whose bbox intersects the padded rectangle.
2. **Widen-and-retry** (`RoutingControl._findRoute` in `web/app.js`) - tries margins `[0.02, 0.08, 0.25]` degrees in order, since a route needing a third comune in between start/end needs a wider net than the tight rectangle around the two points alone. Bounded to 3 tiers so a genuinely out-of-coverage pair fails fast instead of pulling in half of Italy at the widest margin. Doesn't stop at the first margin that finds *a* route - a real case (Trento → Pergine Valsugana) already finds a complete route at the tightest margin, but the second tier's one extra comune reveals a meaningfully cheaper, flatter alternative through it - so it compares cost across margins up through the second tier, only going to the expensive third tier (which can pull in dozens of comuni) when nothing routable was found yet at all.
3. **`mergeRoutingGraphs(files)`** - loads each candidate's `.bin` (parallel `fetch`), decodes it, and merges into one `ngraph.graph` instance keyed by OSM node id (shared ids across files collapse into one node automatically - the property Loading strategy's whole design depends on). `multigraph: true` keeps parallel edges (e.g. both directions of a divided carriageway) as distinct links rather than one silently overwriting the other. Merged graphs are cached by their sorted slug-set key (`mergedGraphCache`) so panning/re-routing within the same comune set doesn't re-parse anything.
4. **`findRoute(start, end, graph, coordByOsmId)`** - snaps each endpoint to its nearest graph node (linear scan - fine at the node counts a handful of merged comuni produce, no spatial index needed), then runs `ngraph.path`'s A* with `edgeCost` as the link cost and the admissible straight-line heuristic above. If the true destination node isn't reachable at all (typically because the only physical way onward is a non-cyclable road, already excluded from the graph), falls back to `_nearestReachableNode` - a BFS from the start over the merged graph - to return a **partial** route showing how far a rider can actually get, rather than a flat "no route".

## Where things live

| Piece | File |
|---|---|
| Per-comune graph export | `scripts/build_routing_graph.py` |
| Cost function (pipeline/batch side) | `code/ltsbikeplan/domain/routing_cost.py` |
| Binary decode + cost function (client) + A* glue | `web/routing.js` |
| UI (pick points, panel, elevation profile, route summary) | `web/app.js`'s `RoutingControl` |
| Per-comune bbox/`has_routing` index | `web/data/comuni_index.json` (`scripts/build_comuni_index.py`) |
