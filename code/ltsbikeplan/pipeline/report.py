from __future__ import annotations

import os
import shutil
import subprocess

from ltsbikeplan.assets import asset_path
from ltsbikeplan.services.report_service import ReportContext, ReportService
from ltsbikeplan.utils import sanitize_city_name


def run_report(city: str, data_dir: str, images_dir: str) -> None:
    context = ReportContext(
        city_sanitized=sanitize_city_name(city),
        data_dir=data_dir,
        code_dir="",
        images_dir=images_dir,
    )
    report_service = ReportService()
    markdown_content = report_service.build_markdown(context)

    os.makedirs(context.city_img_path, exist_ok=True)
    md_file_path = os.path.join(context.city_img_path, "report.md")
    with open(md_file_path, "w") as file_handle:
        file_handle.write(markdown_content)

    html_file_path = os.path.join(context.city_img_path, "report.html")
    if shutil.which("pandoc") is None:
        return
    command = ["pandoc", "-s", md_file_path, "-c", str(asset_path("report.css")), "--metadata", "title=LTSBikePlan Report", "-o", html_file_path]
    subprocess.run(command, check=True)
