from sentinel3_burned_area.processing import process_range


def main() -> None:
    input_dir = "/home/fremen/workspaces/GM/projects/copernicus/burned_area/data"
    output_dir = "/home/fremen/workspaces/GM/projects/calabria2026/seasonal/data/raw/burned_area/sentinel3_copernicus"
    bbox_file = "/home/fremen/workspaces/GM/projects/calabria2026/seasonal/data/aoi/calabria.geojsonl.json"
    reference_file = None
    years = list(range(2018, 2026))
    months = list(range(1, 13))

    result = process_range(
        years=years,
        months=months,
        data_dir=input_dir,
        output_dir=output_dir,
        aoi_path=bbox_file,
        epsg="EPSG:32633",
        resolution=300,
        reference_raster=reference_file,
    )
    print(result.to_dict())


if __name__ == "__main__":
    main()
