from __future__ import annotations

from .slope_strategies import SlopeCalculatorGDAL, SlopeCalculatorR, SlopeCalculatorRasterioSimple, SlopeCalculatorRichdem


class SlopeService:
    def __init__(self, strategy: str = "v3"):
        self.strategy = strategy

    def apply(self, gdf_edges, dem_path: str):
        if self.strategy == "v1":
            return SlopeCalculatorR.calc_slope(gdf_edges, dem_path)
        if self.strategy == "v2":
            try:
                return SlopeCalculatorGDAL.calc_slope(gdf_edges, dem_path)
            except ModuleNotFoundError as exc:
                if getattr(exc, "name", "") == "osgeo":
                    print("GDAL (osgeo) not available, falling back to rasterio-simple slope strategy.")
                    return SlopeCalculatorRasterioSimple.calc_slope(gdf_edges, dem_path)
                raise
        try:
            return SlopeCalculatorRichdem.calc_slope(gdf_edges, dem_path)
        except ModuleNotFoundError as exc:
            missing = getattr(exc, "name", "")
            if missing in {"richdem", "pkg_resources"}:
                print("RichDEM not available, falling back to slope strategy v2 (GDAL).")
                try:
                    return SlopeCalculatorGDAL.calc_slope(gdf_edges, dem_path)
                except ModuleNotFoundError as gdal_exc:
                    if getattr(gdal_exc, "name", "") == "osgeo":
                        print("GDAL (osgeo) not available, falling back to rasterio-simple slope strategy.")
                        return SlopeCalculatorRasterioSimple.calc_slope(gdf_edges, dem_path)
                    raise
            raise
