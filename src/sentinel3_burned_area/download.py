from __future__ import annotations

import subprocess
from pathlib import Path


DEFAULT_S3_PREFIX = "s3://eodata/CLMS/bio-geophysical/burnt_area/ba_global_300m_monthly_v4"


def build_s3_url(year: int, month: int, s3_prefix: str = DEFAULT_S3_PREFIX) -> str:
    month_str = f"{month:02d}"
    filename = f"c_gls_BA300-NTC_{year}{month_str}010000_GLOBE_S3_V4.0.1.nc"
    return (
        f"{s3_prefix}/{year}/{month_str}/01/"
        f"c_gls_BA300-NTC_{year}{month_str}010000_GLOBE_S3_V4.0.1_nc/{filename}"
    )


def download_month(
    *,
    year: int,
    month: int,
    data_dir: str | Path,
    s3cfg: str | Path,
    s3_prefix: str = DEFAULT_S3_PREFIX,
) -> Path:
    month_str = f"{month:02d}"
    local_folder = Path(data_dir) / str(year) / month_str
    local_folder.mkdir(parents=True, exist_ok=True)
    s3_url = build_s3_url(year, month, s3_prefix=s3_prefix)

    subprocess.run(
        ["s3cmd", "-c", str(s3cfg), "get", s3_url, str(local_folder)],
        check=True,
    )
    return local_folder / Path(s3_url).name


def download_range(
    *,
    years: list[int],
    months: list[int],
    data_dir: str | Path,
    s3cfg: str | Path,
    s3_prefix: str = DEFAULT_S3_PREFIX,
) -> list[str]:
    downloaded: list[str] = []
    for year in years:
        for month in months:
            downloaded.append(
                str(
                    download_month(
                        year=year,
                        month=month,
                        data_dir=data_dir,
                        s3cfg=s3cfg,
                        s3_prefix=s3_prefix,
                    )
                )
            )
    return downloaded
