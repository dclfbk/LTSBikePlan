import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.domain.area_spec import AreaSpec, slugify


class TestSlugify(unittest.TestCase):
    def test_does_not_split_on_hyphen(self):
        # Unlike utils.sanitize_city_name, hyphenated Italian region names
        # must stay intact (Emilia-Romagna, Trentino-Alto Adige, ...).
        self.assertEqual(slugify("Emilia-Romagna"), "Emilia-Romagna")
        self.assertEqual(slugify("Trentino-Alto Adige"), "Trentino-Alto_Adige")

    def test_replaces_spaces_with_underscore(self):
        self.assertEqual(slugify("Provincia di Trento"), "Provincia_di_Trento")

    def test_strips_accents_and_unsafe_characters(self):
        self.assertEqual(slugify("Città di Castello"), "Citta_di_Castello")


class TestAreaSpecFromCity(unittest.TestCase):
    def test_from_city_uses_sanitize_city_name_for_slug(self):
        area = AreaSpec.from_city("Trento, Italy")
        self.assertEqual(area.source, "osmnx")
        self.assertEqual(area.place_query, "Trento, Italy")
        self.assertEqual(area.slug, "Trento")


if __name__ == "__main__":
    unittest.main()
