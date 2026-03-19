# sentinel3-burned-area

Clip the Copernicus monthly Sentinel-3 burned-area product over a defined area of interest and export monthly raster and shapefile outputs.

## Install

```bash
pip install -e .
```

## CLI

Process a dataset over an area of interest:

```bash
sentinel3-ba process \
	--aoi /path/to/aoi.shp \
	--data-dir /path/to/data \
	--output-dir /path/to/output \
	--years 2018-2025 \
	--months 1-12 \
	--epsg EPSG:32633 \
	--resolution 300
```

Download monthly NetCDF files with s3cmd:

```bash
sentinel3-ba download \
	--data-dir /path/to/data \
	--s3cfg /path/to/.s3cfg \
	--years 2018-2025 \
	--months 1-12
```

The `process` command writes monthly outputs for each available month, including:

- `BA_300m_wgs.tif`
- `BA_reproj.tif`
- `BA_reproj_as_ref.tif` when `--reference-raster` is provided
- `mask_ba_binary.tif`
- `polygonized.shp`
- `BA.shp`

It also writes an aggregate shapefile at the root of the output directory and a JSON manifest describing the generated files.

## Python

```python
from sentinel3_burned_area import process_range

result = process_range(
		years=[2020, 2021],
		months=[6, 7, 8],
		data_dir="/path/to/data",
		output_dir="/path/to/output",
		aoi_path="/path/to/aoi.shp",
		epsg="EPSG:32633",
		resolution=300,
)

print(result.to_dict())
```
