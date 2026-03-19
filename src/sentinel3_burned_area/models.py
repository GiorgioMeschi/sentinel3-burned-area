from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class MonthOutputs:
    year: int
    month: int
    netcdf_path: str | None = None
    clipped_raster: str | None = None
    reprojected_raster: str | None = None
    aligned_raster: str | None = None
    binary_mask_raster: str | None = None
    polygonized_shapefile: str | None = None
    monthly_shapefile: str | None = None
    skipped: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProcessRunResult:
    output_dir: str
    aoi_path: str
    data_dir: str
    years: list[int]
    months: list[int]
    epsg: str
    resolution: int
    reference_raster: str | None = None
    merged_shapefile: str | None = None
    manifest_path: str | None = None
    results: list[MonthOutputs] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "aoi_path": self.aoi_path,
            "data_dir": self.data_dir,
            "years": self.years,
            "months": self.months,
            "epsg": self.epsg,
            "resolution": self.resolution,
            "reference_raster": self.reference_raster,
            "merged_shapefile": self.merged_shapefile,
            "manifest_path": self.manifest_path,
            "results": [result.to_dict() for result in self.results],
        }
