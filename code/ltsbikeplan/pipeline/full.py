from __future__ import annotations

from ltsbikeplan.pipeline.sections.accident_analysis import run_accident_analysis
from ltsbikeplan.pipeline.sections.clusters import run_clusters
from ltsbikeplan.pipeline.sections.destination_access import run_destination_access
from ltsbikeplan.pipeline.sections.esda import run_esda
from ltsbikeplan.pipeline.sections.gap_analysis import run_gap_analysis
from ltsbikeplan.pipeline.sections.network_analysis import run_network_analysis
from ltsbikeplan.pipeline.sections.sum_up import run_sum_up


def run_full_sections(data_dir: str, images_dir: str, city: str) -> None:
    run_esda(data_dir, images_dir, city)
    run_clusters(data_dir, images_dir, city)
    run_network_analysis(data_dir, images_dir, city)
    run_gap_analysis(data_dir, images_dir, city)
    run_destination_access(data_dir, images_dir, city)
    run_accident_analysis(data_dir, images_dir, city)
    run_sum_up(data_dir, images_dir, city)
