from __future__ import annotations

from .slope_strategies import SlopeCalculatorR, slope_from_dem


class SlopeService:
    """`strategy` only ever really forks into two paths now: "v1" (R/rpy2,
    a separate implementation, see SlopeCalculatorR) and everything else.
    "v2"/"v3" remain accepted values purely so an existing caller/config
    passing one doesn't break - both resolve to the same slope_from_dem
    (see that function's docstring: GDAL and richdem's own terrain-
    analysis functions turned out to be computing the wrong thing, and
    were replaced by direct DEM point-sampling for every non-R strategy,
    so there's no real behavioural difference between "v2" and "v3" left
    to dispatch on).
    """

    def __init__(self, strategy: str = "v3"):
        self.strategy = strategy

    def apply(self, gdf_edges, dem_path: str):
        if self.strategy == "v1":
            return SlopeCalculatorR.calc_slope(gdf_edges, dem_path)
        return slope_from_dem(gdf_edges, dem_path)
