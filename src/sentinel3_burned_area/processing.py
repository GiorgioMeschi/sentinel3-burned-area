from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.features import shapes
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import shape

from sentinel3_burned_area.models import MonthOutputs, ProcessRunResult


DATA_VARIABLE = "day_of_burn"
MONTHLY_WGS_FILENAME = "BA_300m_wgs.tif"
MONTHLY_REPROJECTED_FILENAME = "BA_reproj.tif"
MONTHLY_ALIGNED_FILENAME = "BA_reproj_as_ref.tif"
MONTHLY_MASK_FILENAME = "mask_ba_binary.tif"
MONTHLY_POLYGONIZED_FILENAME = "polygonized.shp"
MONTHLY_SHAPEFILE_FILENAME = "BA.shp"
MERGED_SHAPEFILE_FILENAME = "BA.shp"


def _month_str(month: int) -> str:
    return f"{month:02d}"


def _build_netcdf_path(data_dir: str | Path, year: int, month: int) -> Path:
    month_str = _month_str(month)
    filename = f"c_gls_BA300-NTC_{year}{month_str}010000_GLOBE_S3_V4.0.1.nc"
    return Path(data_dir) / str(year) / month_str / filename


def _build_output_folder(output_dir: str | Path, year: int, month: int) -> Path:
    return Path(output_dir) / f"{year}_{month}"


def _ensure_geometry(dataframe: gpd.GeoDataFrame, crs: str) -> gpd.GeoDataFrame:
    if dataframe.empty:
        return gpd.GeoDataFrame({"date": pd.Series(dtype="datetime64[ns]")}, geometry=[], crs=crs)
    if dataframe.crs is None:
        return dataframe.set_crs(crs)
    return dataframe.to_crs(crs)


def clip_to_aoi_bbox(
    *,
    year: int,
    month: int,
    data_dir: str | Path,
    output_dir: str | Path,
    aoi_path: str | Path,
) -> tuple[Path | None, Path | None]:
    netcdf_path = _build_netcdf_path(data_dir, year, month)
    if not netcdf_path.exists():
        return None, None

    output_folder = _build_output_folder(output_dir, year, month)
    output_folder.mkdir(parents=True, exist_ok=True)
    output_file = output_folder / MONTHLY_WGS_FILENAME

    bbox = gpd.read_file(aoi_path).to_crs(epsg=4326)
    minx, miny, maxx, maxy = bbox.total_bounds

    with xr.open_dataset(netcdf_path) as dataset:
        clipped = dataset.sel(
            lon=slice(minx, maxx),
            lat=slice(maxy, miny),
        )
        if clipped.sizes.get("lon", 0) == 0 or clipped.sizes.get("lat", 0) == 0:
            return netcdf_path, None
        if DATA_VARIABLE not in clipped:
            raise KeyError(f"Variable '{DATA_VARIABLE}' not found in {netcdf_path}")

        data = clipped[DATA_VARIABLE].squeeze(drop=True).values
        if data.ndim != 2:
            raise ValueError(f"Expected 2D raster for '{DATA_VARIABLE}', got shape {data.shape}")

        height, width = data.shape
        west = float(clipped.lon.min())
        east = float(clipped.lon.max())
        south = float(clipped.lat.min())
        north = float(clipped.lat.max())
        transform = from_bounds(west, south, east, north, width, height)

        with rasterio.open(
            output_file,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=data.dtype,
            crs="EPSG:4326",
            transform=transform,
            compress="LZW",
        ) as dst:
            dst.write(data, 1)

    return netcdf_path, output_file


def reproject_raster(
    *,
    input_raster: str | Path,
    output_raster: str | Path,
    epsg: str,
    resolution: int,
) -> Path:
    input_raster = Path(input_raster)
    output_raster = Path(output_raster)

    with rasterio.open(input_raster) as src:
        transform, width, height = calculate_default_transform(
            src.crs,
            epsg,
            src.width,
            src.height,
            *src.bounds,
            resolution=(resolution, resolution),
        )
        profile = src.profile.copy()
        profile.update(
            crs=epsg,
            transform=transform,
            width=width,
            height=height,
            compress="LZW",
        )

        with rasterio.open(output_raster, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=epsg,
                resampling=Resampling.nearest,
            )

    return output_raster


def align_to_reference(
    *,
    input_raster: str | Path,
    output_raster: str | Path,
    reference_raster: str | Path,
) -> Path:
    input_raster = Path(input_raster)
    output_raster = Path(output_raster)
    reference_raster = Path(reference_raster)

    with rasterio.open(input_raster) as src, rasterio.open(reference_raster) as ref:
        profile = ref.profile.copy()
        profile.update(dtype=src.dtypes[0], count=1, compress="LZW")

        with rasterio.open(output_raster, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=ref.transform,
                dst_crs=ref.crs,
                resampling=Resampling.nearest,
            )

    return output_raster


def write_binary_mask(*, input_raster: str | Path, output_raster: str | Path) -> Path:
    input_raster = Path(input_raster)
    output_raster = Path(output_raster)

    with rasterio.open(input_raster) as src:
        data = src.read(1)
        mask = np.where(data > 0, 1, 0).astype(np.uint8)
        profile = src.profile.copy()
        profile.update(dtype=rasterio.uint8, count=1, compress="LZW", nodata=0)

        with rasterio.open(output_raster, "w", **profile) as dst:
            dst.write(mask, 1)

    return output_raster


def polygonize_raster(*, input_raster: str | Path, output_shapefile: str | Path) -> Path | None:
    input_raster = Path(input_raster)
    output_shapefile = Path(output_shapefile)

    with rasterio.open(input_raster) as src:
        data = src.read(1)
        mask = data > 0
        features = [
            {"geometry": shape(geometry), "CLASSES": int(value)}
            for geometry, value in shapes(data, mask=mask, transform=src.transform)
        ]
        if not features:
            return None
        polygonized = gpd.GeoDataFrame(features, geometry="geometry", crs=src.crs)
        polygonized.to_file(output_shapefile)

    return output_shapefile


def build_monthly_shapefile(
    *,
    polygonized_shapefile: str | Path,
    output_shapefile: str | Path,
    year: int,
    crs: str,
) -> Path:
    polygonized = gpd.read_file(polygonized_shapefile)
    polygonized["date"] = polygonized["CLASSES"].apply(
        lambda value: (pd.to_datetime(f"{year}-01-01") + pd.to_timedelta(int(value) - 1, unit="D")).date()
    )
    monthly = polygonized.drop(columns=["CLASSES"])
    monthly = _ensure_geometry(monthly, crs)
    monthly.to_file(output_shapefile)
    return output_shapefile


def merge_monthly_shapefiles(
    *,
    monthly_shapefiles: list[str],
    output_shapefile: str | Path,
    crs: str,
) -> Path | None:
    frames: list[gpd.GeoDataFrame] = []
    for shapefile in monthly_shapefiles:
        path = Path(shapefile)
        if not path.exists():
            continue
        frame = gpd.read_file(path)
        if frame.empty:
            continue
        frames.append(_ensure_geometry(frame, crs))

    if not frames:
        return None

    merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=crs)
    output_shapefile = Path(output_shapefile)
    merged.to_file(output_shapefile)
    return output_shapefile


def process_month(
    *,
    year: int,
    month: int,
    data_dir: str | Path,
    output_dir: str | Path,
    aoi_path: str | Path,
    epsg: str,
    resolution: int,
    reference_raster: str | Path | None = None,
) -> MonthOutputs:
    result = MonthOutputs(year=year, month=month)

    netcdf_path, clipped_raster = clip_to_aoi_bbox(
        year=year,
        month=month,
        data_dir=data_dir,
        output_dir=output_dir,
        aoi_path=aoi_path,
    )
    result.netcdf_path = str(netcdf_path) if netcdf_path else None
    result.clipped_raster = str(clipped_raster) if clipped_raster else None

    if clipped_raster is None:
        result.skipped = True
        result.reason = "Monthly NetCDF file not found or AOI does not intersect the raster"
        return result

    output_folder = _build_output_folder(output_dir, year, month)
    reprojected_raster = reproject_raster(
        input_raster=clipped_raster,
        output_raster=output_folder / MONTHLY_REPROJECTED_FILENAME,
        epsg=epsg,
        resolution=resolution,
    )
    result.reprojected_raster = str(reprojected_raster)

    final_raster = reprojected_raster
    if reference_raster is not None:
        aligned_raster = align_to_reference(
            input_raster=reprojected_raster,
            output_raster=output_folder / MONTHLY_ALIGNED_FILENAME,
            reference_raster=reference_raster,
        )
        result.aligned_raster = str(aligned_raster)
        final_raster = aligned_raster

    binary_mask = write_binary_mask(
        input_raster=final_raster,
        output_raster=output_folder / MONTHLY_MASK_FILENAME,
    )
    result.binary_mask_raster = str(binary_mask)

    polygonized = polygonize_raster(
        input_raster=final_raster,
        output_shapefile=output_folder / MONTHLY_POLYGONIZED_FILENAME,
    )
    if polygonized is None:
        result.reason = "No burned-area pixels found in monthly raster"
        return result

    result.polygonized_shapefile = str(polygonized)
    monthly_shapefile = build_monthly_shapefile(
        polygonized_shapefile=polygonized,
        output_shapefile=output_folder / MONTHLY_SHAPEFILE_FILENAME,
        year=year,
        crs=epsg,
    )
    result.monthly_shapefile = str(monthly_shapefile)
    return result


def process_range(
    *,
    years: list[int],
    months: list[int],
    data_dir: str | Path,
    output_dir: str | Path,
    aoi_path: str | Path,
    epsg: str = "EPSG:32633",
    resolution: int = 300,
    reference_raster: str | Path | None = None,
    write_manifest: bool = True,
    manifest_path: str | Path | None = None,
) -> ProcessRunResult:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_result = ProcessRunResult(
        output_dir=str(output_dir),
        aoi_path=str(Path(aoi_path)),
        data_dir=str(Path(data_dir)),
        years=years,
        months=months,
        epsg=epsg,
        resolution=resolution,
        reference_raster=str(reference_raster) if reference_raster else None,
    )

    monthly_shapefiles: list[str] = []
    for year in years:
        for month in months:
            result = process_month(
                year=year,
                month=month,
                data_dir=data_dir,
                output_dir=output_dir,
                aoi_path=aoi_path,
                epsg=epsg,
                resolution=resolution,
                reference_raster=reference_raster,
            )
            run_result.results.append(result)
            if result.monthly_shapefile:
                monthly_shapefiles.append(result.monthly_shapefile)

    merged_shapefile = merge_monthly_shapefiles(
        monthly_shapefiles=monthly_shapefiles,
        output_shapefile=output_dir / MERGED_SHAPEFILE_FILENAME,
        crs=epsg,
    )
    run_result.merged_shapefile = str(merged_shapefile) if merged_shapefile else None

    if write_manifest:
        manifest = Path(manifest_path) if manifest_path else output_dir / "processing_manifest.json"
        run_result.manifest_path = str(manifest)
        manifest.write_text(json.dumps(run_result.to_dict(), indent=2), encoding="utf-8")

    return run_result
