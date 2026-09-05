#!/usr/bin/env python3
"""Groups comuni into size-based "peer" clusters, then ranks each
cluster's members by low_stress_share - so the stats page can show
"best/worst of comuni like this one" instead of a single national
ranking, where a small hill town and Roma are never actually comparable.
Written for a new section on the stats page's Italia root view: one
card per cluster, its 3 best (low_stress_share) and 3 worst, top best
one getting a "premio" badge in the UI (web/stats/stats.js), with an
up/down pager to page further into the ranking from either end.

Exports each cluster's FULL ranking (every member's istat_code, best to
worst), not just a top/bottom-N slice - a user paging inward from both
ends hit a real gap in the middle once a cluster ran past a fixed cap
(e.g. rank 43 of 123 in "Città grandi" was neither near the top nor the
bottom, and simply wasn't in the exported data at all - not a rendering
bug, the data plainly didn't reach that far). Journalists (this page's
actual target audience for this section) want a browsable ranking, not
just extremes. Exporting istat_code alone (not the full comune/
provincia/popolazione/... row) keeps this cheap: web/stats/stats.js
already has every comune's full row loaded from italia_comuni_stats.json
for the rest of the page, so the ranking here is just a lightweight
lookup key into that, not a second copy of the same data.

Four-stage grouping, not a single 5-way k-means:
1. A fixed population threshold (METROPOLI_MIN_POPOLAZIONE) carves out an
   explicit "Metropoli" tier first.
2. A second fixed threshold (GRANDI_CITTA_MIN_POPOLAZIONE) carves out a
   "Grandi città" tier just below it.
3. A third fixed threshold (CITTA_GRANDI_MIN_POPOLAZIONE) carves out a
   "Città grandi" tier just below that.
4. K-MEANS_CLUSTERS on log(popolazione)/log(superficie_km2) (z-scored)
   for everyone else, giving the size typology among "normal" comuni.

Why not a single k-means over everyone (the first version of this
script): verified empirically that it doesn't work, at any K from 5 to
8 - Roma (2.7M) and Milano etc. always land in the SAME cluster as
comuni of 15-30k residents, because there are only ~15 Italian comuni
above 200k and not nearly enough of them for k-means (which minimizes
within-cluster variance, not "does this look like a distinct real-world
category") to justify carving off such a tiny group on its own. The
result LOOKED like a bug ("why isn't Roma's cluster showing big-city
numbers") but wasn't one - Roma genuinely was in that cluster, just
diluted by ~1000 much smaller peers sharing it, dragging the reported
population percentiles down to ~9k-29k. A hand-picked threshold for the
one tier where "I know it when I see it" beats an algorithm is a more
honest fit than forcing unsupervised clustering to discover something
it structurally can't with only 2 features and this few outliers.

The SAME dilution recurs one tier down, and was only caught later (a
user looking for Trento - pop. ~119k - on the stats page found no
cluster whose population range came anywhere close to it): with only
~15 comuni above 200k removed, the k-means "rest" pool is still
overwhelmingly comuni under 10k (of ~7900 total), so even its own
biggest-of-the-rest cluster ("Città medie") reported a p25-p75 of
roughly 8k-26k - Trento, Bolzano, Rimini, Pisa and the ~120 other
comuni in the 50k-200k range were genuine members of that cluster, just
drowned out by ~1000 much smaller peers the exact same way Roma was
before. Fixed the same way: a second hand-picked threshold
(CITTA_GRANDI_MIN_POPOLAZIONE) carves that range out as its own tier
before k-means ever sees it, so a mid-size city gets compared against
real peers instead of against every small town in the country.

And the dilution's OPPOSITE - one tier being too COARSE rather than
diluted - showed up in the fixed "Grandi città" tier itself: a flat
>=200k threshold with no further split put Roma (2.75M) in the same
bucket as Catania (297k, ~9x smaller) or Padova (208k, ~13x smaller).
There's no k-means fix for this one either (same reason as before - too
few comuni to cluster meaningfully), so it's the same manual-threshold
treatment one level up: METROPOLI_MIN_POPOLAZIONE carves out the
handful of true metropoli (Roma/Milano/Napoli/Torino/Palermo/Genova)
from the rest of "Grandi città" (Bologna down to Padova/Trieste),
splitting at 500k - chosen because it falls in the real gap between
Genova (566k) and Bologna (391k), so no comune sits ambiguously close
to the line.

Clusters on log(popolazione) and log(superficie_km2) ONLY, z-scored -
not also density or km-of-network, which are largely DERIVED from these
same two numbers (density = popolazione / superficie; a bigger area
tends to have more total road km) and would just double-weight the same
signal rather than add a new one. Log-transformed because both are
extremely right-skewed: without it, k-means' Euclidean distance is
dominated by outliers and everything else collapses into one cluster.

K_MEANS_CLUSTERS=6 (for the non-metropoli tier) is a fixed choice, not
picked via an elbow/silhouette search - for a human-facing "what kind of
comune is this" typology, a small, always-the-same number of nameable
groups is more useful than whatever a metric decides is locally optimal
(which could also produce a different K on every rerun as more comuni
are added to the pipeline). Raised from 5 to 6 purely for the stats
page's own layout (an even number of cards tiles more cleanly than an
odd one) - re-run empirically first to make sure 6 still produced
distinct, nameable groups rather than an arbitrary split of one of the
existing 5 (it did: see CLUSTER_LABELS below for the new "Piccoli comuni
densi" tier this revealed).

Cluster order/labels for the k-means tier are assigned by median
population (descending) - NOT hardcoded per cluster ID, since which
numeric cluster label k-means assigns to which group is arbitrary and
can change between runs. Labels are generic size tiers (CLUSTER_LABELS)
rather than hand-picked per centroid, so this stays correct without
maintenance as the comuni set grows - the population/superficie
interquartile range included in the output is what actually anchors
each label to real numbers for the reader.

CAUTION about population-only ordering: it decides which LABEL STRING
goes with which rank, but the label wording itself ("estesi"=extended
area, "compatti"=compact area, "densi"=high density) describes each
cluster's actual superficie/density, which does NOT always move in lock
step with its population rank - it depends on the current comuni set,
and shifted once already (see CITTA_GRANDI_MIN_POPOLAZIONE's carve-out
above: removing the 50k-200k comuni from the k-means pool changed which
rank ended up with the larger area, silently swapping the meaning of
"estesi" and "compatti" until caught and re-verified against the actual
per-rank area/density numbers, not assumed from the previous run).
Whenever K_MEANS_CLUSTERS or the tier thresholds change, re-run once
and check each rank's real superficie/density (not just population)
before trusting CLUSTER_LABELS' existing order still describes it.

Usage: scripts/build_comuni_clusters.py
"""
from __future__ import annotations

import json
import os

import numpy as np
from sklearn.cluster import KMeans

# The 6 true Italian metropoli (Roma, Milano, Napoli, Torino, Palermo,
# Genova) - see the module docstring's "opposite of dilution" comment for
# why this got carved out of "Grandi città" instead of leaving that tier
# a single flat >=200k bucket spanning a ~13x population range.
METROPOLI_MIN_POPOLAZIONE = 500_000
METROPOLI_LABEL = "Metropoli"

# ~15 Italian comuni are above this (Roma down to Brescia, 201k), of
# which METROPOLI_MIN_POPOLAZIONE above carves off the top 6 - matches
# common-sense "le grandi città" rather than anything derived from the
# data itself. See module docstring for why this tier is a fixed
# threshold and not a k-means cluster like the rest.
GRANDI_CITTA_MIN_POPOLAZIONE = 200_000
GRANDI_CITTA_LABEL = "Grandi città"

# Second manual tier, see the module docstring's "SAME dilution recurs
# one tier down" comment - ~120 Italian comuni (Trento, Bolzano, Rimini,
# Pisa, ...) sit in this range, a real peer group that k-means alone
# couldn't tell apart from the thousands of much smaller comuni below it.
CITTA_GRANDI_MIN_POPOLAZIONE = 50_000
CITTA_GRANDI_LABEL = "Città grandi"

K_MEANS_CLUSTERS = 6

# Ordered largest-population-median first (for the k-means tier, i.e.
# excluding Metropoli/Grandi città/Città grandi above) - together with
# those 3 fixed tiers, 9 cluster cards total. If K_MEANS_CLUSTERS
# changes, this needs matching entries - and re-verifying against real
# per-rank area/density numbers, see the CAUTION in the module docstring.
#
# Checked empirically against the actual 6-way split (not assumed from
# the previous 5-way one, which had "estesi"/"compatti" in the opposite
# positions - see that CAUTION): by median population, rank 2 ("Piccoli
# comuni densi") sits ABOVE rank 3 ("Piccoli comuni estesi") despite a
# similar population range, because it's a genuinely distinct type - tiny
# area, ~540 residents/km² median, the densest tier of all 8, previously
# hidden inside "Comuni medio-piccoli". Ranks 3/4 ("estesi"/"compatti")
# land at similar, LOWER population than rank 2, and there the naming is
# literal again: rank 3's median area is roughly 3x rank 4's (46-86 km²
# vs 15-27 km², ~34 vs ~56 residents/km²).
CLUSTER_LABELS = [
    "Città medie",
    "Comuni medio-piccoli",
    "Piccoli comuni densi",
    "Piccoli comuni estesi",
    "Piccoli comuni compatti",
    "Piccoli borghi",
]

def _cluster_output(
    label: str,
    members: list,
    population: np.ndarray,
    superficie: np.ndarray,
    popolazione_soglia_min: int | None = None,
    popolazione_soglia_max: int | None = None,
) -> dict:
    """popolazione_soglia_min/max are the REAL defining threshold for the
    3 fixed-population tiers (Metropoli/Grandi città/Città grandi) -
    None for the 6 k-means tiers below them, which have no such rule (see
    module docstring). The UI (web/stats/stats.js) prefers these over
    popolazione_p25/p75 when present: for a fixed tier, "50.000-200.000
    abitanti" (the actual rule) is more meaningful than "57.776-97.510"
    (the interquartile range of whoever happens to be in it right now,
    which reads like an approximation of something that's actually exact)."""
    members = sorted(members, key=lambda r: r["low_stress_share"], reverse=True)
    return {
        "label": label,
        "comuni_count": len(members),
        "popolazione_p25": round(float(np.percentile(population, 25))),
        "popolazione_p75": round(float(np.percentile(population, 75))),
        "popolazione_soglia_min": popolazione_soglia_min,
        "popolazione_soglia_max": popolazione_soglia_max,
        # Whole km², not round(x, 1) - a value that happens to land on a
        # whole number (56.0) prints as "56" once this JSON round-trips
        # through JS (no trailing ".0" in JS's default number->string),
        # while its neighbour (234.5) keeps a decimal - the same range
        # then reads as "56-234.5", inconsistent precision on the two
        # ends of one range for no real reason (km² doesn't need
        # fractional precision at this scale anyway).
        "superficie_p25": round(float(np.percentile(superficie, 25))),
        "superficie_p75": round(float(np.percentile(superficie, 75))),
        # Full ranking, best to worst, istat_code only - see module
        # docstring for why this replaced a top/bottom-30 cap: it's the
        # join key into italia_comuni_stats.json's own already-loaded
        # rows (web/stats/stats.js's state.comuniByIstat), not a second
        # copy of comune/provincia/popolazione/... for every member.
        "ranking": [r["istat_code"] for r in members],
    }


def main() -> None:
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    comuni_path = os.path.join(repo_root, "web", "data", "italia_comuni_stats.json")
    out_path = os.path.join(repo_root, "web", "data", "italia_comuni_clusters.json")

    with open(comuni_path) as file_handle:
        comuni = json.load(file_handle)

    valid = [
        r
        for r in comuni
        if r.get("popolazione")
        and r.get("superficie_km2")
        and r.get("low_stress_share") is not None
        and r.get("provincia")
        and r.get("regione")
    ]
    skipped = len(comuni) - len(valid)
    print(f"Clustering {len(valid)} comuni (skipped {skipped} missing popolazione/superficie/low_stress_share/provincia/regione)")

    metropoli = [r for r in valid if r["popolazione"] >= METROPOLI_MIN_POPOLAZIONE]
    grandi_citta = [
        r for r in valid
        if GRANDI_CITTA_MIN_POPOLAZIONE <= r["popolazione"] < METROPOLI_MIN_POPOLAZIONE
    ]
    citta_grandi = [
        r for r in valid
        if CITTA_GRANDI_MIN_POPOLAZIONE <= r["popolazione"] < GRANDI_CITTA_MIN_POPOLAZIONE
    ]
    rest = [r for r in valid if r["popolazione"] < CITTA_GRANDI_MIN_POPOLAZIONE]
    print(
        f"  {len(metropoli)} in 'Metropoli' (>= {METROPOLI_MIN_POPOLAZIONE:,} ab.), "
        f"{len(grandi_citta)} in 'Grandi città' ({GRANDI_CITTA_MIN_POPOLAZIONE:,}-{METROPOLI_MIN_POPOLAZIONE:,} ab.), "
        f"{len(citta_grandi)} in 'Città grandi' ({CITTA_GRANDI_MIN_POPOLAZIONE:,}-{GRANDI_CITTA_MIN_POPOLAZIONE:,} ab.), "
        f"{len(rest)} for k-means"
    )

    clusters_out = [
        _cluster_output(
            METROPOLI_LABEL,
            metropoli,
            np.array([r["popolazione"] for r in metropoli], dtype=float),
            np.array([r["superficie_km2"] for r in metropoli], dtype=float),
            popolazione_soglia_min=METROPOLI_MIN_POPOLAZIONE,
            popolazione_soglia_max=None,  # open-ended - Roma is the real max, but stating that as a "threshold" would misrepresent it as a rule rather than just where the data happens to end
        ),
        _cluster_output(
            GRANDI_CITTA_LABEL,
            grandi_citta,
            np.array([r["popolazione"] for r in grandi_citta], dtype=float),
            np.array([r["superficie_km2"] for r in grandi_citta], dtype=float),
            popolazione_soglia_min=GRANDI_CITTA_MIN_POPOLAZIONE,
            popolazione_soglia_max=METROPOLI_MIN_POPOLAZIONE,
        ),
        _cluster_output(
            CITTA_GRANDI_LABEL,
            citta_grandi,
            np.array([r["popolazione"] for r in citta_grandi], dtype=float),
            np.array([r["superficie_km2"] for r in citta_grandi], dtype=float),
            popolazione_soglia_min=CITTA_GRANDI_MIN_POPOLAZIONE,
            popolazione_soglia_max=GRANDI_CITTA_MIN_POPOLAZIONE,
        ),
    ]

    population = np.array([r["popolazione"] for r in rest], dtype=float)
    superficie = np.array([r["superficie_km2"] for r in rest], dtype=float)
    log_features = np.column_stack([np.log10(population), np.log10(superficie)])
    mean = log_features.mean(axis=0)
    std = log_features.std(axis=0)
    scaled = (log_features - mean) / std

    kmeans = KMeans(n_clusters=K_MEANS_CLUSTERS, random_state=42, n_init=10)
    labels = kmeans.fit_predict(scaled)

    # Order raw cluster IDs by median population descending, so
    # CLUSTER_LABELS[0] always lands on the biggest-of-the-rest cluster
    # regardless of which arbitrary ID k-means happened to assign it.
    cluster_ids = sorted(
        range(K_MEANS_CLUSTERS),
        key=lambda cid: -np.median(population[labels == cid]),
    )

    for rank, cid in enumerate(cluster_ids):
        members_idx = np.where(labels == cid)[0]
        members = [rest[i] for i in members_idx]
        label = CLUSTER_LABELS[rank] if rank < len(CLUSTER_LABELS) else f"Cluster {rank + 1}"
        clusters_out.append(_cluster_output(label, members, population[members_idx], superficie[members_idx]))

    with open(out_path, "w") as file_handle:
        json.dump(clusters_out, file_handle, ensure_ascii=False)

    print(f"Wrote {out_path} ({len(clusters_out)} clusters)")
    for cluster in clusters_out:
        print(
            f"  {cluster['label']}: {cluster['comuni_count']} comuni, "
            f"pop {cluster['popolazione_p25']}-{cluster['popolazione_p75']}, "
            f"superficie {cluster['superficie_p25']}-{cluster['superficie_p75']} km²"
        )


if __name__ == "__main__":
    main()
