import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.services.area_index_service import AmbiguousAreaError, AreaNotFoundError, AreaResolver, compute_comuni_superficie_km2

# Minimal fixtures shaped like the real osmit-estratti topojson indices
# (verified live against https://osmit-estratti.wmcloud.org/output/topojson/
# on 2026-08-14), so AreaResolver can be tested without a network call.
_REGIONS = {
    "type": "Topology",
    "objects": {
        "limits_IT_regions": {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "properties": {
                        "name": "Trentino-Alto Adige",
                        "istat": "04",
                        "reg_istat_code": "04",
                        ".osm.pbf": "pbf/regioni/04_Trentino-Alto_Adige.osm.pbf",
                        ".gpkg": "gpkg/regioni/04_Trentino-Alto_Adige.gpkg",
                    }
                }
            ],
        }
    },
}

_PROVINCES = {
    "type": "Topology",
    "objects": {
        "limits_IT_provinces": {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "properties": {
                        "name": "Provincia di Trento",
                        "istat": "022",
                        "reg_istat_code": "04",
                        "prov_istat_code": "022",
                        ".osm.pbf": "pbf/province/022_Provincia_di_Trento.osm.pbf",
                        ".gpkg": "gpkg/province/022_Provincia_di_Trento.gpkg",
                    }
                }
            ],
        }
    },
}

_MUNICIPALITIES = {
    "type": "Topology",
    "objects": {
        "limits_IT_municipalities": {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "properties": {
                        "name": "Trento",
                        "istat": "022205",
                        "reg_istat_code": "04",
                        "prov_istat_code": "022",
                        "com_istat_code": "022205",
                        ".osm.pbf": "pbf/comuni/022205_Trento.osm.pbf",
                        ".gpkg": "gpkg/comuni/022205_Trento.gpkg",
                    }
                },
                {
                    "properties": {
                        "name": "San Michele all'Adige",
                        "istat": "022157",
                        ".osm.pbf": "pbf/comuni/022157.osm.pbf",
                        ".gpkg": "gpkg/comuni/022157.gpkg",
                    }
                },
                {
                    "properties": {
                        "name": "Sanzeno",
                        "istat": "022163",
                        ".osm.pbf": "pbf/comuni/022163.osm.pbf",
                        ".gpkg": "gpkg/comuni/022163.gpkg",
                    }
                },
                # osmit-estratti has real entries with a null name; the
                # resolver must skip these rather than crash on .lower().
                {"properties": {"name": None, "istat": "999999"}},
            ],
        }
    },
}


class TestAreaResolver(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        cache_dir = os.path.join(self.tmp_dir.name, "_cache", "osmit_index")
        os.makedirs(cache_dir, exist_ok=True)
        for filename, payload in [
            ("limits_IT_regions.json", _REGIONS),
            ("limits_IT_provinces.json", _PROVINCES),
            ("limits_IT_municipalities.json", _MUNICIPALITIES),
        ]:
            with open(os.path.join(cache_dir, filename), "w") as file_handle:
                json.dump(payload, file_handle)
        self.resolver = AreaResolver(cache_dir=self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_resolves_comune_by_exact_name_without_level(self):
        area = self.resolver.resolve("Trento")
        self.assertEqual(area.level, "comune")
        self.assertEqual(area.istat_code, "022205")
        self.assertEqual(area.slug, "Trento")
        self.assertEqual(area.pbf_url, "https://osmit-estratti.wmcloud.org/output/pbf/comuni/022205_Trento.osm.pbf")

    def test_resolves_provincia_when_level_given(self):
        area = self.resolver.resolve("Trento", level="provincia")
        self.assertEqual(area.level, "provincia")
        self.assertEqual(area.name, "Provincia di Trento")
        self.assertEqual(area.istat_code, "022")

    def test_resolves_by_istat_code(self):
        area = self.resolver.resolve("anything", istat="022205")
        self.assertEqual(area.name, "Trento")

    def test_hyphenated_region_name_preserved_in_slug(self):
        area = self.resolver.resolve("Trentino", level="regione")
        self.assertEqual(area.slug, "Trentino-Alto_Adige")

    def test_ambiguous_substring_match_raises(self):
        with self.assertRaises(AmbiguousAreaError):
            self.resolver.resolve("San", level="comune")

    def test_unknown_area_raises_not_found(self):
        with self.assertRaises(AreaNotFoundError):
            self.resolver.resolve("Nonexistent Place", level="comune")

    def test_null_name_entries_are_skipped(self):
        # Would raise AttributeError on None.lower() if not skipped.
        with self.assertRaises(AreaNotFoundError):
            self.resolver.resolve("999999-does-not-match-by-name", level="comune")


class TestComputeComuniSuperficie(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        cache_dir = os.path.join(self.tmp_dir.name, "_cache", "osmit_index")
        os.makedirs(cache_dir, exist_ok=True)
        # A plain GeoJSON FeatureCollection, not real topojson - GDAL's
        # file-format sniffing (what geopandas.read_file uses under the
        # hood) reads either the same way, and a hand-written topojson arc
        # encoding isn't worth the complexity just for a test fixture. Two
        # ~0.01°-square comuni near Trento's real coordinates.
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Trento", "istat": "022205"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[11.10, 46.05], [11.11, 46.05], [11.11, 46.06], [11.10, 46.06], [11.10, 46.05]]],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"name": "Lavis", "istat": "022103"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[11.10, 46.15], [11.12, 46.15], [11.12, 46.17], [11.10, 46.17], [11.10, 46.15]]],
                    },
                },
            ],
        }
        with open(os.path.join(cache_dir, "limits_IT_municipalities.json"), "w") as file_handle:
            json.dump(geojson, file_handle)
        self.cache_dir = self.tmp_dir.name

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_returns_positive_area_keyed_by_istat_code(self):
        result = compute_comuni_superficie_km2(self.cache_dir)
        self.assertIn("022205", result)
        self.assertIn("022103", result)
        self.assertGreater(result["022205"], 0)
        # The second comune's polygon is roughly twice as wide and tall as
        # the first's (0.02° vs 0.01°) - should be roughly 4x the area.
        self.assertGreater(result["022103"], result["022205"] * 3)


if __name__ == "__main__":
    unittest.main()
