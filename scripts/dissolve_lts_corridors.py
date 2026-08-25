#!/usr/bin/env python3
"""SOLUZIONE 2 (non ancora collegata alla pipeline) - da rivedere/testare
prima di un run reale.

Perche' esiste: build_national_tiles.sh mostra a bassa quota (z4-11) solo
lo skeleton stradale per classe (motorway/trunk/primary/secondary),
indipendentemente dall'LTS - provato ad aggiungere un secondo filtro
lts+centrality per evidenziare le strade a basso stress, ma i singoli
archi del grafo (il tratto tra due incroci consecutivi) sono quasi sempre
troppo corti (mediana 10-20m, verificato sia in citta' che in comuni
rurali) per essere visibili a quello zoom - tippecanoe li scarta in fase
di semplificazione prima ancora di valutare il filtro. Serve unire i
tratti contigui con lo stesso LTS in un'unica polilinea piu' lunga PRIMA
di arrivare a tippecanoe.

Cosa fa: legge il parquet gia' calcolato di un comune
(<slug>_all_lts.parquet, le stesse colonne che oggi finiscono nel .geojson
via regenerate_geojson.py), raggruppa gli archi per valore di `lts`, unisce
le geometrie di ciascun gruppo con shapely.ops.linemerge (fonde solo i
tratti che si toccano per un estremo - non fonde archi con lo stesso LTS
ma geometricamente distanti), e scrive un nuovo parquet
<slug>_lts_corridors.parquet con un record per ciascun corridoio risultante:
geometry, lts, length (ricalcolata sul corridoio unito, non piu' sul
singolo arco), centrality (max tra gli archi che lo compongono - "quanto
e' importante il punto piu' importante di questo corridoio").

NON tocca ne' sostituisce <slug>_all_lts.parquet (quello resta la fonte
per il rendering per-comune a z12+, il click, i popup, i "Tratti da
valutare" - tutto quello che serve il dettaglio per-arco). Questo e' un
prodotto derivato, pensato solo per alimentare il branch "highlight" del
tileset nazionale a bassa quota.

Uso (per un comune):
    python3 scripts/dissolve_lts_corridors.py data/Trento/Trento_all_lts.parquet data/Trento/Trento_lts_corridors.parquet

Per tutta Italia (quando si ricalcolano i comuni), va richiamato una volta
per comune - vedi il TODO in fondo per come agganciarlo a
build_national_tiles.sh una volta verificato che funziona:
  - rigenerare (o aggiungere accanto a) i .geojson che build_national_tiles.sh
    passa a tippecanoe per il branch "highlight", usando l'output di
    questo script invece del parquet grezzo
  - ri-eseguire scripts/lts_zoom_analysis.py / lts_zoom_analysis2.py contro
    i *_lts_corridors.parquet risultanti (non i *_all_lts.parquet) per
    ricalcolare le soglie di centrality: il numero di corridoi per comune
    e' molto minore del numero di archi, quindi i percentili 0.0395/0.052
    calcolati sugli archi NON sono validi sui corridoi - vanno ricavati
    da zero sulla nuova popolazione.
  - riverificare con lo stesso script di test
    (chiedimelo di nuovo quando sei a questo punto, tipo
    /tmp/lts_tile_density_test.sh adattato) che i corridoi risultanti
    siano davvero visibili nei tile decodificati a z4-11, non solo che
    passino il filtro.
"""
from __future__ import annotations

import argparse
import sys

import geopandas as gpd
import pandas as pd
from shapely.ops import linemerge, unary_union


def dissolve_corridors(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    rows = []
    for lts_value, group in gdf.groupby("lts"):
        if lts_value is None or lts_value < 0:
            continue
        merged = linemerge(unary_union(group.geometry.tolist()))
        # linemerge puo' restituire una singola LineString (tutto si e'
        # fuso in un solo corridoio) o una MultiLineString (piu' corridoi
        # separati che non si toccano) - normalizza a una lista di
        # LineString, un record per corridoio.
        geoms = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
        for geom in geoms:
            rows.append(
                {
                    "geometry": geom,
                    "lts": int(lts_value),
                    "length": geom.length,  # in CRS metrico del gdf in ingresso
                    "centrality": group["centrality"].max(),
                }
            )
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs=gdf.crs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("parquet_path", help="<slug>_all_lts.parquet gia' calcolato")
    parser.add_argument("out_path", help="dove scrivere <slug>_lts_corridors.parquet")
    args = parser.parse_args()

    gdf = gpd.read_parquet(args.parquet_path, columns=["highway", "lts", "centrality", "geometry"])
    if gdf.crs is None or not gdf.crs.is_projected:
        print(
            f"ATTENZIONE: CRS non metrico ({gdf.crs}) - length sui corridoi non sara' in metri. "
            "Il parquet e' salvato in WORKING_CRS (EPSG:3035, vedi regenerate_geojson.py) quindi "
            "questo di norma non dovrebbe succedere.",
            file=sys.stderr,
        )

    corridors = dissolve_corridors(gdf)
    corridors.to_parquet(args.out_path)
    print(f"{len(gdf)} archi -> {len(corridors)} corridoi, scritto in {args.out_path}")


if __name__ == "__main__":
    main()
