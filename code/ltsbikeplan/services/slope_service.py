from __future__ import annotations

from .slope_strategies import SlopeCalculatorGDAL, SlopeCalculatorR, SlopeCalculatorRichdem


class SlopeService:
    def __init__(self, strategy: str = "v3"):
        self.strategy = strategy

    def apply(self, gdf_edges, dem_path: str):
        if self.strategy == "v1":
            return SlopeCalculatorR.calc_slope(gdf_edges, dem_path)
        if self.strategy == "v2":
            return SlopeCalculatorGDAL.calc_slope(gdf_edges, dem_path)
        return SlopeCalculatorRichdem.calc_slope(gdf_edges, dem_path)
