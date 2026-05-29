from __future__ import annotations

import os

from .common import city_output_dir


def run_sum_up(data_dir: str, images_dir: str, city: str) -> None:
    out_dir = city_output_dir(images_dir, city)

    gap_q = os.path.join(out_dir, "gap_quadrants.html")
    risk_h = os.path.join(out_dir, "risk_accidents_hexagon.html")

    with open(gap_q, "w") as file_handle:
        file_handle.write("<html><body><h3>Gap quadrants summary placeholder</h3></body></html>")

    with open(risk_h, "w") as file_handle:
        file_handle.write("<html><body><h3>Risk-accidents hexagon summary placeholder</h3></body></html>")
