from sentinel3_burned_area.download import download_range


def main() -> None:
    years = list(range(2018, 2026))
    months = list(range(1, 13))
    data_dir = "/home/fremen/workspaces/GM/projects/copernicus/burned_area/data"
    s3cfg = "/home/fremen/workspaces/GM/projects/copernicus/.s3cfg"

    downloaded = download_range(
        years=years,
        months=months,
        data_dir=data_dir,
        s3cfg=s3cfg,
    )
    print(downloaded)


if __name__ == "__main__":
    main()

