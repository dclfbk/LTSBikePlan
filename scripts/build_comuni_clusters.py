#!/usr/bin/env python3
"""Groups comuni into size-based "peer" clusters, then ranks each
cluster's members by low_stress_share - so the stats page can show
"best/worst of comuni like this one" instead of a single national
ranking, where a small hill town and Roma are never actually comparable.
Written for a new section on the stats page's Italia root view: one
card per cluster, its 3 best (low_stress_share) and 3 worst, top best
one getting a "premio" badge in the UI (web/stats/stats.js).

Two-stage grouping, not a single 5-way k-means:
1. A fixed population threshold (GRANDI_CITTA_MIN_POPOLAZIONE) carves out
   an explicit "Grandi città" tier first.
2. K-MEANS_CLUSTERS on log(popolazione)/log(superficie_km2) (z-scored)
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

Clusters on log(popolazione) and log(superficie_km2) ONLY, z-scored -
not also density or km-of-network, which are largely DERIVED from these
same two numbers (density = popolazione / superficie; a bigger area
tends to have more total road km) and would just double-weight the same
signal rather than add a new one. Log-transformed because both are
extremely right-skewed: without it, k-means' Euclidean distance is
dominated by outliers and everything else collapses into one cluster.

K_MEANS_CLUSTERS=4 (for the non-metropoli tier) is a fixed choice, not
picked via an elbow/silhouette search - for a human-facing "what kind of
comune is this" typology, a small, always-the-same number of nameable
groups is more useful than whatever a metric decides is locally optimal
(which could also produce a different K on every rerun as more comuni
are added to the pipeline).

Cluster order/labels for the k-means tier are assigned by median
population (descending) - NOT hardcoded per cluster ID, since which
numeric cluster label k-means assigns to which group is arbitrary and
can change between runs. Labels are generic size tiers (CLUSTER_LABELS)
rather than hand-picked per centroid, so this stays correct without
maintenance as the comuni set grows - the population/superficie
interquartile range included in the output is what actually anchors
each label to real numbers for the reader.

Usage: scripts/build_comuni_clusters.py
"""
from __future__ import annotations

import json
import os

import numpy as np
from sklearn.cluster import KMeans

# ~15 Italian comuni are above this (Roma down to Brescia, 201k) -
# matches common-sense "le grandi città" rather than anything derived
# from the data itself. See module docstring for why this tier is a
# fixed threshold and not a k-means cluster like the rest.
GRANDI_CITTA_MIN_POPOLAZIONE = 200_000
GRANDI_CITTA_LABEL = "Grandi città"

K_MEANS_CLUSTERS = 5
# Exported per side (best/worst), not just the 3 actually shown at once -
# the stats page pages through these in blocks of 3 via up/down arrows
# rather than only ever offering the fixed top-3/bottom-3. Capped well
# below a cluster's full member count (some clusters run to ~1900
# comuni) since the point is "browse a bit further into the ranking",
# not ship the entire national dataset through this one JSON file.
TOP_N = 30

# Ordered largest-population-median first (for the k-means tier, i.e.
# excluding Grandi città above) - together with that fixed tier, 6
# cluster cards total. If K_MEANS_CLUSTERS changes, this needs matching
# entries. "estesi"/"compatti" (ranks 3/4, checked empirically) aren't
# just decoration - those two land at similar population but rank 3's
# median area is roughly 10x rank 4's, i.e. genuinely low- vs
# high-density small comuni, not just "a bit smaller".
CLUSTER_LABELS = [
    "Città medie",
    "Comuni medio-piccoli",
    "Piccoli comuni estesi",
    "Piccoli comuni compatti",
    "Piccoli borghi",
]

SUMMARY_FIELDS = [
    "istat_code",
    "comune",
    "provincia",
    "regione",
    "popolazione",
    "superficie_km2",
    "total_km",
    "low_stress_share",
    "priority_intervention_km",
]


def _summarize(record: dict) -> dict:
    return {field: record.get(field) for field in SUMMARY_FIELDS}


def _cluster_output(label: str, members: list, population: np.ndarray, superficie: np.ndarray) -> dict:
    members = sorted(members, key=lambda r: r["low_stress_share"], reverse=True)
    return {
        "label": label,
        "comuni_count": len(members),
        "popolazione_p25": round(float(np.percentile(population, 25))),
        "popolazione_p75": round(float(np.percentile(population, 75))),
        "superficie_p25": round(float(np.percentile(superficie, 25)), 1),
        "superficie_p75": round(float(np.percentile(superficie, 75)), 1),
        "top": [_summarize(r) for r in members[:TOP_N]],
        "bottom": [_summarize(r) for r in members[-TOP_N:][::-1]],
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

    grandi_citta = [r for r in valid if r["popolazione"] >= GRANDI_CITTA_MIN_POPOLAZIONE]
    rest = [r for r in valid if r["popolazione"] < GRANDI_CITTA_MIN_POPOLAZIONE]
    print(f"  {len(grandi_citta)} in 'Grandi città' (>= {GRANDI_CITTA_MIN_POPOLAZIONE:,} ab.), {len(rest)} for k-means")

    clusters_out = [
        _cluster_output(
            GRANDI_CITTA_LABEL,
            grandi_citta,
            np.array([r["popolazione"] for r in grandi_citta], dtype=float),
            np.array([r["superficie_km2"] for r in grandi_citta], dtype=float),
        )
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
