import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import pandas as pd

    from ltsbikeplan.pipeline.compute_lts import derive_cycleway_type

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "geopandas/osmnx (geo extras) not installed")
class TestDeriveCyclewayType(unittest.TestCase):
    def test_no_cycleway_tags_returns_nan(self):
        row = pd.Series({"cycleway": None, "cycleway:left": None, "cycleway:right": None, "cycleway:both": None})
        self.assertTrue(pd.isna(derive_cycleway_type(row)))

    def test_all_no_returns_nan(self):
        row = pd.Series({"cycleway": "no", "cycleway:left": "no", "cycleway:right": "no", "cycleway:both": "no"})
        self.assertTrue(pd.isna(derive_cycleway_type(row)))

    def test_plain_cycleway_tag_wins(self):
        row = pd.Series({"cycleway": "lane", "cycleway:left": None, "cycleway:right": None, "cycleway:both": None})
        self.assertEqual(derive_cycleway_type(row), "lane")

    def test_falls_back_to_side_specific_tag(self):
        row = pd.Series({"cycleway": "no", "cycleway:left": "track", "cycleway:right": "no", "cycleway:both": None})
        self.assertEqual(derive_cycleway_type(row), "track")

    def test_missing_columns_do_not_raise(self):
        row = pd.Series({"highway": "residential"})
        self.assertTrue(pd.isna(derive_cycleway_type(row)))


if __name__ == "__main__":
    unittest.main()
