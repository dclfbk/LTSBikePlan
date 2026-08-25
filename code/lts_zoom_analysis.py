import glob, time, collections
import pyarrow.parquet as pq
import numpy as np

files = sorted(glob.glob("data/*/*_all_lts.parquet"))
print(f"{len(files)} files", flush=True)

major = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link"}
tier1 = {"motorway", "motorway_link", "trunk", "trunk_link"}
tier2 = tier1 | {"primary", "primary_link"}
tier3 = major

t0 = time.time()
n_total = 0
lts_counts_all = collections.Counter()
tier_lts_counts = {
    "tier1(z4-5,today)": collections.Counter(),
    "tier2(z6,today)": collections.Counter(),
    "tier3(z7-11,today)": collections.Counter(),
}
lts12_count = 0
lts12_len = 0.0
lts123_count = 0
lts123_len = 0.0
total_len = 0.0
centrality_lts12 = []
errors = 0

for i, f in enumerate(files):
    try:
        t = pq.read_table(f, columns=["highway", "lts", "length", "centrality"])
    except Exception:
        errors += 1
        continue
    highway = t.column("highway").to_pylist()
    lts = t.column("lts").to_pylist()
    length = t.column("length").to_pylist()
    centrality = t.column("centrality").to_pylist()
    n = len(lts)
    n_total += n
    for hv, lv, le, ce in zip(highway, lts, length, centrality):
        lv = int(lv) if lv is not None else -1
        le = le or 0.0
        lts_counts_all[lv] += 1
        total_len += le
        if hv in tier1:
            tier_lts_counts["tier1(z4-5,today)"][lv] += 1
        if hv in tier2:
            tier_lts_counts["tier2(z6,today)"][lv] += 1
        if hv in tier3:
            tier_lts_counts["tier3(z7-11,today)"][lv] += 1
        if lv in (1, 2):
            lts12_count += 1
            lts12_len += le
            if ce is not None:
                centrality_lts12.append(ce)
        if lv in (1, 2, 3):
            lts123_count += 1
            lts123_len += le
    if i % 1000 == 0:
        print(f"  ...{i}/{len(files)} files, {n_total} edges so far, {time.time() - t0:.0f}s elapsed", flush=True)

print(f"\nDONE in {time.time() - t0:.0f}s, errors={errors}", flush=True)
print(f"total edges nationwide: {n_total}", flush=True)
print(f"total length nationwide (km): {total_len / 1000:.0f}", flush=True)
print("\noverall LTS distribution:", flush=True)
for k in sorted(lts_counts_all):
    print(f"  lts={k}: {lts_counts_all[k]} ({100 * lts_counts_all[k] / n_total:.1f}%)", flush=True)

for tname, c in tier_lts_counts.items():
    tot = sum(c.values())
    print(f"\n--- {tname} (n={tot}) ---", flush=True)
    for k in sorted(c):
        if tot:
            print(f"  lts={k}: {c[k]} ({100 * c[k] / tot:.1f}%)", flush=True)

print(f"\nCandidate z4-7 selection (LTS 1+2, any road class): {lts12_count} edges, {lts12_len / 1000:.0f} km", flush=True)
print(f"Candidate z8-11 selection (LTS 1+2+3, any road class): {lts123_count} edges, {lts123_len / 1000:.0f} km", flush=True)

if centrality_lts12:
    arr = np.array(centrality_lts12)
    print(f"\ncentrality among LTS1/2 edges: n={len(arr)}, mean={arr.mean():.4g}, median={np.median(arr):.4g}", flush=True)
    for pct in [50, 75, 90, 95, 99]:
        thr = np.percentile(arr, pct)
        keep = (arr >= thr).sum()
        print(
            f"  p{pct} threshold={thr:.4g} -> keeps {keep} edges "
            f"({100 * keep / len(arr):.1f}% of LTS1/2, {100 * keep / n_total:.2f}% of all edges)",
            flush=True,
        )

print(
    f"\nfor reference, TODAY's tier3(z7-11) baseline size: "
    f"{sum(tier_lts_counts['tier3(z7-11,today)'].values())} edges - this is the known-working scale "
    "(already hit tippecanoe tuning issues per build_national_tiles.sh comments)",
    flush=True,
)
