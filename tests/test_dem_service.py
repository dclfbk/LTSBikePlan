import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

try:
    import numpy as np
    from PIL import Image

    from ltsbikeplan.services.dem_service import _ORIGIN_SHIFT, _lonlat_to_tile, _tile_bounds_3857, decode_terrarium

    GEO_DEPS_AVAILABLE = True
except ImportError:
    GEO_DEPS_AVAILABLE = False


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "Pillow/numpy (geo extras) not installed")
class TestDecodeTerrarium(unittest.TestCase):
    def _make_image(self, r, g, b):
        arr = np.full((2, 2, 3), [r, g, b], dtype=np.uint8)
        return Image.fromarray(arr, mode="RGB")

    def test_zero_rgb_is_minimum_elevation(self):
        # Terrarium spec: elevation = (R*256 + G + B/256) - 32768.
        elevation = decode_terrarium(self._make_image(0, 0, 0))
        self.assertTrue((elevation == -32768).all())

    def test_r_128_is_sea_level(self):
        elevation = decode_terrarium(self._make_image(128, 0, 0))
        self.assertTrue((elevation == 0).all())

    def test_known_offset_from_sea_level(self):
        # R=128,G=200 -> 128*256 + 200 - 32768 = 200m.
        elevation = decode_terrarium(self._make_image(128, 200, 0))
        self.assertTrue((elevation == 200).all())


@unittest.skipUnless(GEO_DEPS_AVAILABLE, "Pillow/numpy (geo extras) not installed")
class TestTileMath(unittest.TestCase):
    def test_zoom_zero_tile_covers_whole_world(self):
        bounds = _tile_bounds_3857(0, 0, 0)
        min_x, min_y, max_x, max_y = bounds
        self.assertAlmostEqual(min_x, -_ORIGIN_SHIFT, places=1)
        self.assertAlmostEqual(max_x, _ORIGIN_SHIFT, places=1)
        self.assertAlmostEqual(min_y, -_ORIGIN_SHIFT, places=1)
        self.assertAlmostEqual(max_y, _ORIGIN_SHIFT, places=1)

    def test_lonlat_to_tile_matches_known_slippy_map_tile(self):
        # Trento center, zoom 13 - verified against a live Mapterhorn fetch.
        x, y = _lonlat_to_tile(11.1217, 46.0679, 13)
        self.assertEqual((x, y), (4349, 2912))

    def test_north_hemisphere_tile_y_increases_southward(self):
        x_north, y_north = _lonlat_to_tile(11.0, 46.5, 10)
        x_south, y_south = _lonlat_to_tile(11.0, 45.5, 10)
        self.assertLess(y_north, y_south)


if __name__ == "__main__":
    unittest.main()
