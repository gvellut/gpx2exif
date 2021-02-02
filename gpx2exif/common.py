import click

delta_option = click.option(
    "-d",
    "--delta",
    "delta",
    help=(
        "Time shift to apply to the photo Date Time Original EXIF tag "
        "to match the date in GPX (see documentation for format). Use if there is a "
        "drift in the camera compared to the GPS recorder or if an offset "
        "is not present in the EXIF. (default: no shift)"
    ),
    required=False,
)

tolerance_option = click.option(
    "-t",
    "--tolerance",
    "tolerance",
    help=(
        "Tolerance if time of photo is not inside the time range of the GPX track. "
        "(default: 10s)"
    ),
    required=False,
    default="10s",
)

ignore_offset_option = click.option(
    "-o",
    "--ignore-offset",
    "is_ignore_offset",
    is_flag=True,
    help=(
        "Flag to indicate that the OffsetTimeOriginal should not be used (time of "
        "images is assumed UTC). Use --delta to compensate for both timezone and "
        "drift."
    ),
    required=False,
)

head_option = click.option(
    "-h",
    "--head",
    "is_head",
    is_flag=True,
    help=(
        "Flag to indicate if the tool should just output the times of the first "
        "10 track points in the GPX and the DateTimeOriginal tag of the first "
        "10 images (useful for setting the --delta)."
    ),
    required=False,
)

kml_option = click.option(
    "-k",
    "--kml",
    "kml_output_path",
    help=(
        "Path for a KML output file with placemarks for the photos (useful for "
        "checking the delta)"
    ),
    required=False,
)

kml_thumbnail_size_option = click.option(
    "--kml_thumbnail_size",
    "kml_thumbnail_size",
    default=400,
    type=click.INT,
    help=("Pixel size of the image popup in the KML"),
    required=False,
)

update_images_option = click.option(
    "--update-images/--no-update-images",
    "is_update_images",
    default=True,
    help=(
        "Flag to indicate that the images should not be udpated and only a KML will "
        "generated"
    ),
    required=False,
)

clear_option = click.option(
    "-c",
    "--clear",
    "is_clear",
    is_flag=True,
    help=(
        "Flag to indicate that the GPS EXIF fields should be cleared if no position "
        "can be computed for the photo."
    ),
    required=False,
)
