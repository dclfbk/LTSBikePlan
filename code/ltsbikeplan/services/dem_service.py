from __future__ import annotations

import math
import os
from io import BytesIO
from typing import Optional, Tuple

import numpy as np
import rasterio
import requests
from PIL import Image
from rasterio.transform import from_bounds

MAPTERHORN_TILE_URL = "https://tiles.mapterhorn.com/{z}/{x}/{y}.webp"
WEB_MERCATOR_CRS = "EPSG:3857"
_ORIGIN_SHIFT = math.pi * 6378137.0  # half circumference of Web Mercator, meters


def _lonlat_to_tile(lon: float, lat: float, zoom: int) -> Tuple[int, int]:
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _tile_bounds_3857(x: int, y: int, zoom: int) -> Tuple[float, float, float, float]:
    n = 2**zoom
    tile_size_m = 2 * _ORIGIN_SHIFT / n
    min_x = -_ORIGIN_SHIFT + x * tile_size_m
    max_x = min_x + tile_size_m
    max_y = _ORIGIN_SHIFT - y * tile_size_m
    min_y = max_y - tile_size_m
    return (min_x, min_y, max_x, max_y)


def decode_terrarium(image: Image.Image) -> np.ndarray:
    """Terrarium RGB elevation encoding (verified against a live Mapterhorn
    tile over Trento: decoded values 183-742m match the real terrain range
    around the city center)."""
    arr = np.asarray(image.convert("RGB"), dtype=np.float64)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    return (r * 256 + g + b / 256) - 32768


class MapterhornDemService:
    """Fetches an elevation GeoTIFF for an area's bounding box from
    Mapterhorn's open Terrarium-encoded tiles (Italy coverage: 10m).

    Output CRS is EPSG:3857 (native tile grid) - SlopeService/slope_strategies
    already read the DEM's CRS dynamically from the raster, so no downstream
    change is needed to consume this instead of a manually-downloaded
    TINITALY tile.
    """

    def __init__(self, zoom: int = 13, tile_size: int = 512, cache_dir: Optional[str] = None):
        self.zoom = zoom
        self.tile_size = tile_size
        self.cache_dir = cache_dir

    def _fetch_tile_image(self, x: int, y: int) -> Image.Image:
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
            cached_path = os.path.join(self.cache_dir, f"{self.zoom}_{x}_{y}.webp")
            if os.path.exists(cached_path):
                return Image.open(cached_path)
            response = requests.get(MAPTERHORN_TILE_URL.format(z=self.zoom, x=x, y=y), timeout=60)
            response.raise_for_status()
            with open(cached_path, "wb") as file_handle:
                file_handle.write(response.content)
            return Image.open(cached_path)

        response = requests.get(MAPTERHORN_TILE_URL.format(z=self.zoom, x=x, y=y), timeout=60)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))

    def fetch_dem(self, bbox_4326: Tuple[float, float, float, float], out_path: str) -> str:
        west, south, east, north = bbox_4326
        x_nw, y_nw = _lonlat_to_tile(west, north, self.zoom)
        x_se, y_se = _lonlat_to_tile(east, south, self.zoom)
        x_min, x_max = sorted((x_nw, x_se))
        y_min, y_max = sorted((y_nw, y_se))

        cols = x_max - x_min + 1
        rows = y_max - y_min + 1
        mosaic = np.zeros((rows * self.tile_size, cols * self.tile_size), dtype=np.float32)

        for row_idx, ty in enumerate(range(y_min, y_max + 1)):
            for col_idx, tx in enumerate(range(x_min, x_max + 1)):
                elevation = decode_terrarium(self._fetch_tile_image(tx, ty))
                r0, c0 = row_idx * self.tile_size, col_idx * self.tile_size
                mosaic[r0 : r0 + self.tile_size, c0 : c0 + self.tile_size] = elevation

        left, _, _, top = _tile_bounds_3857(x_min, y_min, self.zoom)
        _, bottom, right, _ = _tile_bounds_3857(x_max, y_max, self.zoom)
        transform = from_bounds(left, bottom, right, top, mosaic.shape[1], mosaic.shape[0])

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with rasterio.open(
            out_path,
            "w",
            driver="GTiff",
            height=mosaic.shape[0],
            width=mosaic.shape[1],
            count=1,
            dtype="float32",
            crs=WEB_MERCATOR_CRS,
            transform=transform,
        ) as dst:
            dst.write(mosaic, 1)
        return out_path
