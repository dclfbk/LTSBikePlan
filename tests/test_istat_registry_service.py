import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.services.istat_registry_service import IstatRegistryService

_PROVINCIA_COLUMN = "Denominazione dell'Unità territoriale sovracomunale \n(valida a fini statistici)"
_CAPOLUOGO_COLUMN = "Flag Comune capoluogo di Provincia/Città metropolitana/libero consorzio"


def _write_fixture_xlsx(path):
    # Column subset IstatRegistryService.load() actually reads, shaped like
    # the real "Elenco-comuni-italiani.xlsx" (verified live 2026-08-15).
    df = pd.DataFrame(
        [
            {
                "Denominazione in italiano": "Trento",
                "Denominazione Regione": "Trentino-Alto Adige/Südtirol",
                _PROVINCIA_COLUMN: "Trento",
                _CAPOLUOGO_COLUMN: 1,
                "Codice Comune formato numerico": 22205,
            },
            {
                "Denominazione in italiano": "Lavis",
                "Denominazione Regione": "Trentino-Alto Adige/Südtirol",
                _PROVINCIA_COLUMN: "Trento",
                _CAPOLUOGO_COLUMN: 0,
                "Codice Comune formato numerico": 22103,
            },
            {
                "Denominazione in italiano": "Agliè",
                "Denominazione Regione": "Piemonte",
                _PROVINCIA_COLUMN: "Torino",
                _CAPOLUOGO_COLUMN: 0,
                "Codice Comune formato numerico": 1001,
            },
        ]
    )
    df.to_excel(path, sheet_name="CODICI al 21_02_2026", index=False)


class TestIstatRegistryService(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.service = IstatRegistryService(cache_dir=self.tmp_dir.name)
        _write_fixture_xlsx(self.service._path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_capoluogo_di_regione_matched_by_name_and_regione(self):
        registry = self.service.load()
        self.assertTrue(registry["022205"]["capoluogo_regione"])
        self.assertTrue(registry["022205"]["capoluogo_provincia"])

    def test_capoluogo_di_provincia_without_being_capoluogo_di_regione(self):
        # Reuses Trento's own provincia/regione tagging but isn't "Trento"
        # by name, so REGIONE_CAPOLUOGO must not match it.
        registry = self.service.load()
        self.assertFalse(registry["022103"]["capoluogo_provincia"])
        self.assertFalse(registry["022103"]["capoluogo_regione"])

    def test_regular_comune_has_both_flags_false(self):
        registry = self.service.load()
        self.assertFalse(registry["001001"]["capoluogo_provincia"])
        self.assertFalse(registry["001001"]["capoluogo_regione"])

    def test_istat_code_is_zero_padded_to_six_digits(self):
        registry = self.service.load()
        self.assertIn("001001", registry)
        self.assertNotIn("1001", registry)

    def test_regione_and_provincia_names_carried_through(self):
        registry = self.service.load()
        self.assertEqual(registry["022205"]["regione"], "Trentino-Alto Adige/Südtirol")
        self.assertEqual(registry["022205"]["provincia"], "Trento")

    def test_does_not_redownload_a_fresh_cache(self):
        with mock.patch("ltsbikeplan.services.istat_registry_service.requests.get") as mock_get:
            self.service.load()
        mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
