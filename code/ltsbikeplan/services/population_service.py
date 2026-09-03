from __future__ import annotations

import datetime
import io
import os
import time
import zipfile
from typing import Dict

import pandas as pd
import requests

# Population WAS considered unsourceable - see istat_registry_service.py's
# own module docstring: the SDMX/I.Stat warehouse (dataflow
# 22_289_DF_DCIS_POPRES1_1) returned "NoRecordsFound" on every query tried
# on 2026-08-15. This is a different, much simpler ISTAT product: POSAS
# ("Popolazione residente per età, sesso e stato civile") ships as a
# plain per-comune bulk-download ZIP, no API/auth/SDMX involved - the same
# source https://cruscotto-italia.dati.gov.it (AgID, github.com/AgID/
# cruscotto-italia, etl/sources/demografia.py) uses. Verified live
# 2026-09-03: reachable with no geo/WAF restriction from this environment,
# 7896 comuni, Italy-wide total ~58.9M matches the real population - the
# earlier SDMX dead end was a wrong-endpoint problem, not a
# data-doesn't-exist problem.
POSAS_URL_TEMPLATE = "https://demo.istat.it/data/posas/POSAS_{year}_it_Comuni.zip"

# Same reasoning as IstatRegistryService's cache: population moves slowly
# (ISTAT republishes this file about once a year, every January) so a
# day-scale cache would just re-download an unchanged ~8.5MB file on every
# pipeline run for no reason.
_CACHE_MAX_AGE_SECONDS = 30 * 24 * 3600

# ISTAT typically publishes "population as of 1 January <year>" partway
# through that same year - at any given moment the freshest file on the
# server could be next year's (already published), this year's, or still
# only last year's. Tries newest-first and falls back, same sequence
# cruscotto-italia's own ETL uses, rather than hardcoding one year that
# will eventually 404.
def _candidate_years() -> list[int]:
    current = datetime.date.today().year
    return [current + 1, current, current - 1]


class PopulationService:
    """Resident population per comune, from ISTAT's POSAS bulk file."""

    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.join(cache_dir, "_cache", "population")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cached_zip_path(self, year: int) -> str:
        return os.path.join(self.cache_dir, f"POSAS_{year}_it_Comuni.zip")

    def _download_if_stale(self) -> str:
        """Returns the path to a valid cached ZIP, (re)downloading the
        newest available year's file if the cache is missing/stale.
        """
        for year in _candidate_years():
            path = self._cached_zip_path(year)
            if os.path.exists(path) and (time.time() - os.path.getmtime(path)) <= _CACHE_MAX_AGE_SECONDS:
                return path

        last_error: Exception | None = None
        for year in _candidate_years():
            url = POSAS_URL_TEMPLATE.format(year=year)
            try:
                response = requests.get(url, timeout=120)
                response.raise_for_status()
            except requests.RequestException as error:
                last_error = error
                continue
            path = self._cached_zip_path(year)
            with open(path, "wb") as file_handle:
                file_handle.write(response.content)
            return path

        raise RuntimeError(f"Could not download POSAS population data for any candidate year: {last_error}")

    def load(self) -> Dict[str, int]:
        """Returns {istat_code (6-digit zero-padded string): resident
        population}. Età==999 is POSAS's own per-comune all-ages total
        row - summing the individual per-age rows instead would double
        count (verified against Roma/Firenze/Napoli's known populations).
        """
        zip_path = self._download_if_stale()
        with zipfile.ZipFile(zip_path) as archive:
            csv_name = next(name for name in archive.namelist() if name.endswith(".csv"))
            with archive.open(csv_name) as csv_file:
                df = pd.read_csv(
                    io.TextIOWrapper(csv_file, encoding="utf-8-sig"),
                    sep=";",
                    skiprows=1,
                    usecols=["Codice comune", "Età", "Totale"],
                    dtype={"Codice comune": str},
                )

        totals = df[df["Età"] == 999]
        return dict(zip(totals["Codice comune"], totals["Totale"].astype(int)))
