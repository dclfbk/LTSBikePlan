from __future__ import annotations

import os
import re
import time
import unicodedata
from typing import Dict

import pandas as pd
import requests


# Accent/case/punctuation-insensitive key for matching a comune name
# across two different sources that don't spell it identically (see
# IstatRegistryService.load_by_name's own docstring for the Sardegna
# legacy-istat-code case this exists for).
def normalize_comune_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(name))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())

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
        self._df: pd.DataFrame | None = None

    def _download_if_stale(self) -> None:
        if os.path.exists(self._path) and (time.time() - os.path.getmtime(self._path)) <= _CACHE_MAX_AGE_SECONDS:
            return
        response = requests.get(ISTAT_COMUNI_URL, timeout=60)
        response.raise_for_status()
        with open(self._path, "wb") as file_handle:
            file_handle.write(response.content)

    def _dataframe(self) -> pd.DataFrame:
        if self._df is None:
            self._download_if_stale()
            # sheet_name=0 (not the literal sheet name) - the real sheet
            # name embeds the file's own revision date (e.g. "CODICI al
            # 21_02_2026"), which changes on every ISTAT refresh.
            self._df = pd.read_excel(self._path, sheet_name=0)
        return self._df

    @staticmethod
    def _entry_from_row(row) -> dict:
        regione = row["Denominazione Regione"]
        comune_name = row["Denominazione in italiano"]
        return {
            "regione": regione,
            "provincia": row["Denominazione dell'Unità territoriale sovracomunale \n(valida a fini statistici)"],
            "capoluogo_provincia": bool(row["Flag Comune capoluogo di Provincia/Città metropolitana/libero consorzio"]),
            "capoluogo_regione": REGIONE_CAPOLUOGO.get(regione) == comune_name,
        }

    def load(self) -> Dict[str, dict]:
        """Returns {istat_code (6-digit zero-padded string): {"regione":
        str, "provincia": str, "capoluogo_provincia": bool,
        "capoluogo_regione": bool}}.
        """
        registry: Dict[str, dict] = {}
        for _, row in self._dataframe().iterrows():
            istat_code = str(int(row["Codice Comune formato numerico"])).zfill(6)
            registry[istat_code] = self._entry_from_row(row)
        return registry

    def load_by_name(self) -> Dict[str, dict]:
        """Same entries as load(), keyed by normalize_comune_name(...) of
        the comune's current official Italian name instead of istat_code.

        Exists for comuni whose istat_code has since changed - Sardegna's
        provincial reorganizations (the 8-province split, then its
        reversal down to Sassari/Nuoro/Oristano/Sud Sardegna plus Cagliari
        città metropolitana) renumbered practically every Sardinian
        comune, but this project's already-processed data (parquet/
        pmtiles, some of it years old) still carries whatever istat_code
        was current when it was fetched - e.g. Fonni as "091024" (a
        legacy Nuoro-province code), not this registry's current
        "114013". A straight istat_code lookup silently misses all ~374
        of them (confirmed 2026-09 - see [[sardegna_legacy_istat_codes]]
        if that memory exists). The comune name itself didn't change,
        so matching on that instead recovers every one of them - verified
        374/374 matched this way, no residual misses.
        """
        by_name: Dict[str, dict] = {}
        for _, row in self._dataframe().iterrows():
            key = normalize_comune_name(row["Denominazione in italiano"])
            by_name[key] = self._entry_from_row(row)
        return by_name
