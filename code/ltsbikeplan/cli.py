from __future__ import annotations

import argparse
import os
import shutil
import warnings
from pathlib import Path

from .config import AppConfig
from .runtime_requirements import MANUAL_OPTIONAL_INPUTS, MANUAL_REQUIRED_INPUTS


def cmd_fetch(city: str, config: AppConfig) -> None:
    from .pipeline.fetch import run_fetch

    dem_path = os.environ.get("LTSBP_DEM_PATH", str(config.data_dir / "w51075_s10.tif"))
    strategy = os.environ.get("LTSBP_SLOPE_STRATEGY", "v3")
    run_fetch(city, str(config.data_dir), str(config.images_dir), dem_path, strategy)


def cmd_compute_lts(config: AppConfig) -> None:
    from .pipeline.compute_lts import run_compute_lts

    run_compute_lts(str(config.data_dir))


def cmd_maps(city: str, config: AppConfig) -> None:
    from .pipeline.maps import generate_h3_choropleth_map, generate_lts_map

    generate_lts_map(str(config.data_dir), str(config.images_dir), city)
    generate_h3_choropleth_map(str(config.data_dir), str(config.images_dir), city)


def cmd_report(city: str, config: AppConfig) -> None:
    from .pipeline.report import run_report

    run_report(city, str(config.data_dir), str(config.images_dir))


def cmd_run_all(city: str, config: AppConfig, include_report: bool) -> None:
    cmd_fetch(city, config)
    cmd_compute_lts(config)
    cmd_maps(city, config)
    if include_report:
        cmd_report(city, config)


def cmd_run_full(city: str, config: AppConfig, include_report: bool) -> None:
    from .pipeline.full import run_full_sections

    cmd_fetch(city, config)
    cmd_compute_lts(config)
    cmd_maps(city, config)
    run_full_sections(str(config.data_dir), str(config.images_dir), city)
    if include_report:
        cmd_report(city, config)


def cmd_doctor(city: str, config: AppConfig) -> None:
    print("Manual required inputs:")
    for item in MANUAL_REQUIRED_INPUTS:
        env_var = item.get("env_var")
        default_path = item.get("default_path")
        value = os.environ.get(env_var, default_path)
        abs_path = Path(value)
        if not abs_path.is_absolute():
            abs_path = config.repo_root / value
        status = "OK" if abs_path.exists() else "MISSING"
        print(f"- {item['name']}: {status} -> {abs_path}")

    print("\nManual optional inputs:")
    for item in MANUAL_OPTIONAL_INPUTS:
        print(f"- {item['name']}: {item['path_pattern']}")

    pandoc_ok = shutil.which("pandoc") is not None
    print("\nSystem tools:")
    print(f"- pandoc (required for HTML report): {'OK' if pandoc_ok else 'MISSING'}")

    print(f"\nCity context: {city}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LTSBikePlan command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Download and pre-process city data")
    fetch_parser.add_argument("--city", required=True, help="City/place name")

    subparsers.add_parser("compute-lts", help="Compute and export LTS artifacts")

    maps_parser = subparsers.add_parser("maps", help="Generate LTS HTML maps")
    maps_parser.add_argument("--city", required=True, help="City/place name")

    report_parser = subparsers.add_parser("report", help="Generate markdown/html report")
    report_parser.add_argument("--city", required=True, help="City/place name")

    run_all_parser = subparsers.add_parser("run", help="Run fetch + compute-lts + maps (+report)")
    run_all_parser.add_argument("--city", required=True, help="City/place name")
    run_all_parser.add_argument("--with-report", action="store_true", help="Generate report at the end")

    run_full_parser = subparsers.add_parser("run-full", help="Run full pipeline including ESDA/cluster/network sections")
    run_full_parser.add_argument("--city", required=True, help="City/place name")
    run_full_parser.add_argument("--with-report", action="store_true", help="Generate report at the end")

    doctor_parser = subparsers.add_parser("doctor", help="Show required manual inputs and status")
    doctor_parser.add_argument("--city", required=False, default="Trento, Italy", help="City/place name")

    return parser


def main(argv: list[str] | None = None) -> int:
    warnings.filterwarnings("ignore", message=r"networkx backend defined more than once: nx-loopback", category=RuntimeWarning)
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_project_layout()

    if args.command == "fetch":
        cmd_fetch(args.city, config)
    elif args.command == "compute-lts":
        cmd_compute_lts(config)
    elif args.command == "maps":
        cmd_maps(args.city, config)
    elif args.command == "report":
        cmd_report(args.city, config)
    elif args.command == "run":
        cmd_run_all(args.city, config, args.with_report)
    elif args.command == "run-full":
        cmd_run_full(args.city, config, args.with_report)
    elif args.command == "doctor":
        cmd_doctor(args.city, config)
    else:
        parser.error(f"Unsupported command: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
