from __future__ import annotations

import os
import time
from typing import Dict

import pandas as pd
import requests

# Permanent link (per ISTAT's own site: it "rimane invariato ad ogni
# aggiornamento del file" - stays the same across every refresh). Verified
# live 2026-08-15: 7894 comuni, with regione/provincia hierarchy and a
# capoluogo-di-provincia flag. Does NOT include population or superficie:
# - superficie is instead computed from the comuni boundary geometry
#   AreaResolver already caches - see
#   area_index_service.py::compute_comuni_superficie_km2.
# - population is sourced separately, from ISTAT's POSAS bulk file - see
#   population_service.py's own module docstring. An earlier
#   investigation (2026-08-15) of the SDMX/I.Stat data warehouse
#   (dataflow 22_289_DF_DCIS_POPRES1_1) dead-ended on every query
#   returning "NoRecordsFound" - that was the wrong endpoint, not a
#   population-isn't-available problem; POSAS resolved it (2026-09-03).
ISTAT_COMUNI_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx"

# Administrative-boundary changes (comuni mergers, new province) happen a
# handful of times a year at most - a day-scale cache like AreaResolver's
# osmit-estratti index would just re-download an unchanged 1.2MB file on
# every run for no reason.
_CACHE_MAX_AGE_SECONDS = 30 * 24 * 3600

# Regione -> its capoluogo comune, by name rather than ISTAT code - easier
# to audit in review than a wall of numeric codes, and this doesn't need to
# be efficient (20 entries, looked up 7894 times at most). Effectively
# permanent. Trentino-Alto Adige/Südtirol is the one debatable case (an
# autonomous region with two provincial capitals, Trento and Bolzano) -
# follows the conventional choice of Trento. Regione names must match
# ISTAT's own "Denominazione Regione" spelling exactly, bilingual ones
# included.
REGIONE_CAPOLUOGO = {
    "Piemonte": "Torino",
    "Valle d'Aosta/Vallée d'Aoste": "Aosta",
    "Liguria": "Genova",
    "Lombardia": "Milano",
    "Trentino-Alto Adige/Südtirol": "Trento",
    "Veneto": "Venezia",
    "Friuli-Venezia Giulia": "Trieste",
    "Emilia-Romagna": "Bologna",
    "Toscana": "Firenze",
    "Umbria": "Perugia",
    "Marche": "Ancona",
    "Lazio": "Roma",
    "Abruzzo": "L'Aquila",
    "Molise": "Campobasso",
    "Campania": "Napoli",
    "Puglia": "Bari",
    "Basilicata": "Potenza",
    "Calabria": "Catanzaro",
    "Sicilia": "Palermo",
    "Sardegna": "Cagliari",
}


class IstatRegistryService:
    """Regione/provincia hierarchy + capoluogo flags for every Italian
    comune, from ISTAT's official "Elenco dei comuni italiani". See
    ISTAT_COMUNI_URL above for what this file does and doesn't cover.
    """

    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.join(cache_dir, "_cache", "istat_registry")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._path = os.path.join(self.cache_dir, "Elenco-comuni-italiani.xlsx")

    def _download_if_stale(self) -> None:
        if os.path.exists(self._path) and (time.time() - os.path.getmtime(self._path)) <= _CACHE_MAX_AGE_SECONDS:
            return
        response = requests.get(ISTAT_COMUNI_URL, timeout=60)
        response.raise_for_status()
        with open(self._path, "wb") as file_handle:
            file_handle.write(response.content)

    def load(self) -> Dict[str, dict]:
        """Returns {istat_code (6-digit zero-padded string): {"regione":
        str, "provincia": str, "capoluogo_provincia": bool,
        "capoluogo_regione": bool}}.
        """
        self._download_if_stale()
        # sheet_name=0 (not the literal sheet name) - the real sheet name
        # embeds the file's own revision date (e.g. "CODICI al
        # 21_02_2026"), which changes on every ISTAT refresh.
        df = pd.read_excel(self._path, sheet_name=0)

        registry: Dict[str, dict] = {}
        for _, row in df.iterrows():
            istat_code = str(int(row["Codice Comune formato numerico"])).zfill(6)
            regione = row["Denominazione Regione"]
            comune_name = row["Denominazione in italiano"]
            registry[istat_code] = {
                "regione": regione,
                "provincia": row["Denominazione dell'Unità territoriale sovracomunale \n(valida a fini statistici)"],
                "capoluogo_provincia": bool(row["Flag Comune capoluogo di Provincia/Città metropolitana/libero consorzio"]),
                "capoluogo_regione": REGIONE_CAPOLUOGO.get(regione) == comune_name,
            }
        return registry
