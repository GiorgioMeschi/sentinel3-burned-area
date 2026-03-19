from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_int_sequence(value: str | None, *, default: list[int] | None = None) -> list[int]:
    if value is None:
        if default is None:
            raise ValueError("A value is required")
        return default

    values: set[int] = set()
    for chunk in value.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            if end < start:
                raise ValueError(f"Invalid range '{part}'")
            values.update(range(start, end + 1))
            continue
        values.add(int(part))

    if not values:
        if default is None:
            raise ValueError("At least one integer value is required")
        return default
    return sorted(values)


def _infer_years_from_data_dir(data_dir: Path) -> list[int]:
    years: list[int] = []
    for child in data_dir.iterdir():
        if child.is_dir() and child.name.isdigit() and len(child.name) == 4:
            years.append(int(child.name))
    return sorted(years)


def _process_command(args: argparse.Namespace) -> int:
    from sentinel3_burned_area.processing import process_range

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    aoi_path = Path(args.aoi)
    if not aoi_path.exists():
        raise FileNotFoundError(f"AOI file not found: {aoi_path}")

    years = _parse_int_sequence(args.years, default=_infer_years_from_data_dir(data_dir))
    if not years:
        raise ValueError("No years were provided and none could be inferred from the data directory")

    months = _parse_int_sequence(args.months, default=list(range(1, 13)))
    invalid_months = [month for month in months if month < 1 or month > 12]
    if invalid_months:
        raise ValueError(f"Months must be between 1 and 12, got {invalid_months}")

    result = process_range(
        years=years,
        months=months,
        data_dir=data_dir,
        output_dir=args.output_dir,
        aoi_path=aoi_path,
        epsg=args.epsg,
        resolution=args.resolution,
        reference_raster=args.reference_raster,
        write_manifest=not args.no_manifest,
        manifest_path=args.manifest,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def _download_command(args: argparse.Namespace) -> int:
    from sentinel3_burned_area.download import download_range

    years = _parse_int_sequence(args.years, default=list(range(2018, 2026)))
    months = _parse_int_sequence(args.months, default=list(range(1, 13)))
    downloaded = download_range(
        years=years,
        months=months,
        data_dir=args.data_dir,
        s3cfg=args.s3cfg,
        s3_prefix=args.s3_prefix,
    )
    print(json.dumps({"downloaded": downloaded}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinel3-ba")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser("process", help="Clip and polygonize monthly burned-area files")
    process_parser.add_argument("--aoi", required=True, help="Vector file describing the area of interest")
    process_parser.add_argument("--data-dir", required=True, help="Directory containing the monthly NetCDF dataset")
    process_parser.add_argument("--output-dir", required=True, help="Directory where outputs will be written")
    process_parser.add_argument("--years", help="Years to process, for example '2018-2020,2024'")
    process_parser.add_argument("--months", help="Months to process, for example '1-3,7,12'")
    process_parser.add_argument("--epsg", default="EPSG:32633", help="Target CRS for reprojected outputs")
    process_parser.add_argument("--resolution", type=int, default=300, help="Target output resolution in map units")
    process_parser.add_argument("--reference-raster", help="Optional raster used to align reprojected outputs")
    process_parser.add_argument("--manifest", help="Optional path for the JSON output manifest")
    process_parser.add_argument("--no-manifest", action="store_true", help="Disable manifest file creation")
    process_parser.set_defaults(func=_process_command)

    download_parser = subparsers.add_parser("download", help="Download monthly NetCDF files from Copernicus S3 storage")
    download_parser.add_argument("--data-dir", required=True, help="Directory where NetCDF files will be stored")
    download_parser.add_argument("--s3cfg", required=True, help="Path to the s3cmd configuration file")
    download_parser.add_argument("--years", help="Years to download, for example '2018-2020,2024'")
    download_parser.add_argument("--months", help="Months to download, for example '1-3,7,12'")
    download_parser.add_argument("--s3-prefix", default="s3://eodata/CLMS/bio-geophysical/burnt_area/ba_global_300m_monthly_v4", help="Base S3 prefix for the monthly files")
    download_parser.set_defaults(func=_download_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
