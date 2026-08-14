from __future__ import annotations

import argparse
import os
import shutil
import sys
import warnings
from pathlib import Path

from .config import AppConfig
from .domain.area_spec import AreaSpec
from .runtime_requirements import MANUAL_OPTIONAL_INPUTS, MANUAL_REQUIRED_INPUTS


def _add_area_args(subparser: argparse.ArgumentParser, required: bool = True) -> None:
    group = subparser.add_mutually_exclusive_group(required=required)
    group.add_argument("--area", help="Region/province/comune or place name, resolved via osmnx/Overpass by default (works anywhere, matching the original paper's tool) - pass --osmit-estratti to use the faster Italy-only pre-built extracts instead")
    group.add_argument("--city", help="Legacy: city/place name resolved via osmnx/Nominatim")
    subparser.add_argument(
        "--osmit-estratti",
        action="store_true",
        help="Resolve --area via the osmit-estratti (Wikimedia Italia) pre-built extracts instead of live OSMnx/Overpass - faster for large regioni/province, Italy only",
    )
    subparser.add_argument(
        "--area-level",
        choices=["comune", "provincia", "regione"],
        default=None,
        help="Disambiguates --area when the name matches at more than one admin level (only used with --osmit-estratti)",
    )
    subparser.add_argument("--istat", default=None, help="ISTAT code, disambiguates --area precisely (only used with --osmit-estratti)")


def resolve_area(args: argparse.Namespace, config: AppConfig) -> AreaSpec:
    if getattr(args, "city", None):
        return AreaSpec.from_city(args.city)

    if not getattr(args, "osmit_estratti", False):
        if args.area_level or args.istat:
            print("--area-level/--istat are ignored without --osmit-estratti (osmnx/Overpass has no ISTAT-level disambiguation)", file=sys.stderr)
        return AreaSpec.from_city(args.area)

    from .services.area_index_service import AreaResolver

    resolver = AreaResolver(cache_dir=str(config.data_dir))
    return resolver.resolve(args.area, level=args.area_level, istat=args.istat)


def cmd_fetch(area: AreaSpec, config: AppConfig) -> None:
    from .pipeline.fetch import run_fetch

    dem_path = os.environ.get("LTSBP_DEM_PATH")
    strategy = os.environ.get("LTSBP_SLOPE_STRATEGY", "v3")
    run_fetch(area, str(config.data_dir), str(config.images_dir), dem_path, strategy)


def cmd_compute_lts(area: AreaSpec, config: AppConfig) -> None:
    from .pipeline.compute_lts import run_compute_lts

    run_compute_lts(str(config.data_dir), area)


def cmd_maps(area: AreaSpec, config: AppConfig) -> None:
    from .pipeline.maps import generate_h3_choropleth_map, generate_lts_map

    generate_lts_map(str(config.data_dir), str(config.images_dir), area.slug)
    generate_h3_choropleth_map(str(config.data_dir), str(config.images_dir), area.slug)


def cmd_report(area: AreaSpec, config: AppConfig) -> None:
    from .pipeline.report import run_report

    run_report(area.slug, str(config.data_dir), str(config.images_dir))


def cmd_run_all(area: AreaSpec, config: AppConfig, include_report: bool) -> None:
    cmd_fetch(area, config)
    cmd_compute_lts(area, config)
    cmd_maps(area, config)
    if include_report:
        cmd_report(area, config)


def cmd_run_full(area: AreaSpec, config: AppConfig, include_report: bool) -> None:
    from .pipeline.full import run_full_sections

    cmd_fetch(area, config)
    cmd_compute_lts(area, config)
    cmd_maps(area, config)
    run_full_sections(str(config.data_dir), str(config.images_dir), area.slug)
    if include_report:
        cmd_report(area, config)


def cmd_doctor(city: str, config: AppConfig) -> None:
    print("Manual required inputs:")
    for item in MANUAL_REQUIRED_INPUTS:
        env_var = item.get("env_var")
        default_path = item.get("default_path")
        value = os.environ.get(env_var, default_path)
        abs_path = Path(value)
        if not abs_path.is_absolute():
            abs_path = config.repo_root / value
        status = "OK" if abs_path.exists() else "MISSING (auto-fetched from Mapterhorn if unset)"
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

    fetch_parser = subparsers.add_parser("fetch", help="Download and pre-process area data")
    _add_area_args(fetch_parser)

    compute_lts_parser = subparsers.add_parser("compute-lts", help="Compute and export LTS artifacts")
    _add_area_args(compute_lts_parser)

    maps_parser = subparsers.add_parser("maps", help="Generate LTS HTML maps")
    _add_area_args(maps_parser)

    report_parser = subparsers.add_parser("report", help="Generate markdown/html report")
    _add_area_args(report_parser)

    run_all_parser = subparsers.add_parser("run", help="Run fetch + compute-lts + maps (+report)")
    _add_area_args(run_all_parser)
    run_all_parser.add_argument("--with-report", action="store_true", help="Generate report at the end")

    run_full_parser = subparsers.add_parser("run-full", help="Run full pipeline including ESDA/cluster/network sections")
    _add_area_args(run_full_parser)
    run_full_parser.add_argument("--with-report", action="store_true", help="Generate report at the end")

    doctor_parser = subparsers.add_parser("doctor", help="Show required manual inputs and status")
    doctor_parser.add_argument("--city", required=False, default="Trento, Italy", help="City/place name")

    return parser


def main(argv: list[str] | None = None) -> int:
    warnings.filterwarnings("ignore", message=r"networkx backend defined more than once: nx-loopback", category=RuntimeWarning)
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_project_layout()

    if args.command == "doctor":
        cmd_doctor(args.city, config)
        return 0

    area = resolve_area(args, config)

    if args.command == "fetch":
        cmd_fetch(area, config)
    elif args.command == "compute-lts":
        cmd_compute_lts(area, config)
    elif args.command == "maps":
        cmd_maps(area, config)
    elif args.command == "report":
        cmd_report(area, config)
    elif args.command == "run":
        cmd_run_all(area, config, args.with_report)
    elif args.command == "run-full":
        cmd_run_full(area, config, args.with_report)
    else:
        parser.error(f"Unsupported command: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
