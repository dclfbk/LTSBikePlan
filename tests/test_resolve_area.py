import argparse
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.cli import resolve_area
from ltsbikeplan.config import AppConfig
from ltsbikeplan.domain.area_spec import AreaSpec


def _config():
    return AppConfig(repo_root=Path("."), code_dir=Path("."), data_dir=Path("data"), images_dir=Path("images"))


class TestResolveArea(unittest.TestCase):
    def test_city_flag_uses_osmnx(self):
        args = argparse.Namespace(city="Trento, Italy", area=None, osmit_estratti=False, area_level=None, istat=None)
        area = resolve_area(args, _config())
        self.assertEqual(area.source, "osmnx")
        self.assertEqual(area.place_query, "Trento, Italy")

    def test_area_flag_defaults_to_osmnx_overpass(self):
        args = argparse.Namespace(city=None, area="Provincia di Trento", osmit_estratti=False, area_level=None, istat=None)
        area = resolve_area(args, _config())
        self.assertEqual(area.source, "osmnx")
        self.assertEqual(area.place_query, "Provincia di Trento")

    def test_area_flag_with_osmit_estratti_uses_the_resolver(self):
        args = argparse.Namespace(city=None, area="Trento", osmit_estratti=True, area_level="comune", istat=None)

        class FakeResolver:
            def __init__(self, cache_dir):
                self.cache_dir = cache_dir

            def resolve(self, name, level=None, istat=None):
                return AreaSpec(name=name, slug=name, source="osmit", level=level, istat_code=istat)

        with mock.patch("ltsbikeplan.services.area_index_service.AreaResolver", FakeResolver):
            area = resolve_area(args, _config())

        self.assertEqual(area.source, "osmit")
        self.assertEqual(area.level, "comune")


if __name__ == "__main__":
    unittest.main()
