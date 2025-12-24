from datetime import datetime, timedelta
import logging
from pathlib import Path
import sys

import click
import exiftool
import pytz

from .common import (
    UpdateConfirmationAbortedException,
    clear_option,
    delta_option,
    delta_tz_option,
    format_timedelta,
    kml_option,
    print_delta,
    process_delta,
    update_images_option,
    update_time_option,
    yes_option,
)

logger = logging.getLogger(__package__)


def _get_image_files(img_fileordirpath):
    """Get list of image files from a file or directory path."""
    if img_fileordirpath.is_file():
        return [str(img_fileordirpath)]
    elif img_fileordirpath.is_dir():
        # Get all non-hidden files in the directory
        files = [
            str(f.resolve())
            for f in sorted(img_fileordirpath.iterdir())
            if f.is_file() and not f.name.startswith(".")
        ]
        return files
    return []


def _build_geotag_params(gpx_filepath, delta, is_clear):
    """Build parameters for exiftool geotag command."""
    params = ["-geotag", str(gpx_filepath)]

    # Handle time offset for geotag matching using -geosync
    if delta != timedelta(0):
        offset_seconds = round(delta.total_seconds())
        params.append(f"-geosync={offset_seconds}")

    # If clear is set, use the geotime option to clear GPS if no match
    if is_clear:
        # Use API option to handle images outside track time range
        params.append("-api")
        params.append("GeoMaxIntSecs=0")

    params.append("-overwrite_original")

    return params


def _build_time_shift_params(delta):
    """Build parameters for exiftool time shift command."""
    offset_seconds = round(delta.total_seconds())
    hours = abs(offset_seconds) // 3600
    minutes = (abs(offset_seconds) % 3600) // 60
    seconds = abs(offset_seconds) % 60

    sign = "+" if offset_seconds >= 0 else "-"
    time_shift = f"{sign}0:0:0 {hours}:{minutes}:{seconds}"

    return [f"-DateTimeOriginal+={time_shift}", "-overwrite_original"]


def _generate_kml_with_exiftool(et, img_files, kml_output_path):
    """
    Generate KML file using exiftool to extract GPS coordinates.
    """
    if not img_files:
        logger.error("No KML output (no files to process)!")
        return

    try:
        # Get GPS data from images
        metadata = et.get_tags(
            img_files,
            tags=[
                "FileName",
                "Directory",
                "GPSLatitude",
                "GPSLongitude",
            ],
        )

        # Filter images that have GPS coordinates
        geotagged = [
            m
            for m in metadata
            if "EXIF:GPSLatitude" in m and "EXIF:GPSLongitude" in m
        ]

        if not geotagged:
            logger.error("No KML output (no georeferenced photos)!")
            return

        # Build KML content
        kml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            "<Document>",
            "  <name>Photo Locations</name>",
        ]

        for m in geotagged:
            filename = m.get("File:FileName", "Unknown")
            directory = m.get("File:Directory", "")
            lat = m.get("EXIF:GPSLatitude", 0)
            lon = m.get("EXIF:GPSLongitude", 0)

            filepath = f"{directory}/{filename}" if directory else filename

            kml_lines.extend(
                [
                    "  <Placemark>",
                    f"    <name>{filename}</name>",
                    f"    <description><![CDATA[{filepath}]]></description>",
                    "    <Point>",
                    f"      <coordinates>{lon},{lat},0</coordinates>",
                    "    </Point>",
                    "  </Placemark>",
                ]
            )

        kml_lines.extend(["</Document>", "</kml>"])

        # Write KML file
        with open(kml_output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(kml_lines))

        logger.info(f"KML file written to: {kml_output_path}")

    except Exception as ex:
        logger.error(f"Error generating KML: {ex}")


@click.command(
    name="exiftool",
    help="Add GPS EXIF tags to local images based on a GPX file using exiftool",
)
@click.argument(
    "gpx_filepath",
    metavar="GPX_FILE",
    type=click.Path(exists=True, resolve_path=True, dir_okay=False),
)
@click.argument(
    "img_fileordirpath",
    metavar="IMAGE_FILE_OR_DIR",
    type=click.Path(exists=True, resolve_path=True),
)
@delta_option
@delta_tz_option
@click.option(
    "--tz",
    "tz",
    help=(
        "Named timezone to apply to the photo times "
        "to match the date in GPX (see documentation for format). "
        "If present, assumes --ignore-offset. "
        "A special value 'auto' will automatically use the local timezone. "
        "[default: no shift (timezone of the image if present)]"
    ),
    required=False,
)
@clear_option
@kml_option
@update_images_option
@update_time_option
@yes_option
@click.pass_context
def exiftool_command(
    ctx,
    gpx_filepath,
    img_fileordirpath,
    delta,
    delta_tz,
    tz,
    is_clear,
    kml_output_path,
    is_update_images,
    is_update_time,
    is_yes,
):
    """
    Add GPS EXIF tags to local images based on a GPX file using exiftool.
    This command uses the exiftool binary with its native -geotag support.
    All GPX processing and position interpolation is handled by exiftool.
    """
    et = None
    try:
        if delta_tz and tz:
            raise click.UsageError("Cannot use --delta-tz and --tz at the same time")

        logger.info("Parsing time shift...")
        delta = process_delta(delta)
        print_delta(delta, "Time")

        # Handle timezone offset
        if tz:
            if tz == "auto":
                # Use local timezone
                local_tz = datetime.now().astimezone().tzinfo
                delta_tz_offset = -local_tz.utcoffset(datetime.now())
            else:
                try:
                    tz_obj = pytz.timezone(tz)
                except pytz.UnknownTimeZoneError as ex:
                    raise click.UsageError(f"Unknown timezone: {tz}") from ex
                # Use current time to get offset (exiftool handles DST itself)
                delta_tz_offset = -tz_obj.utcoffset(datetime.now().replace(tzinfo=None))
            logger.info(f"Timezone offset: {delta_tz_offset}")
        elif delta_tz:
            delta_tz_offset = process_delta([delta_tz])
        else:
            delta_tz_offset = None

        if delta_tz_offset:
            print_delta(delta_tz_offset, "TZ time")
            delta_total = delta + delta_tz_offset
            print_delta(delta_total, "Total time")
        else:
            delta_total = delta

        img_fileordirpath = Path(img_fileordirpath)

        logger.info("Synching EXIF GPS to GPX using exiftool...")

        if not is_update_images:
            logger.warning("The images will not be updated!")
        else:
            if is_update_time:
                fdt = format_timedelta(delta)
                logger.warning(f"The times in the images will be shifted: {fdt}!")

            if not is_yes:
                if not click.confirm("The images will be updated. Confirm?"):
                    raise UpdateConfirmationAbortedException()

        # Use a single ExifToolHelper instance for the whole program run
        # auto_start=True (default) means exiftool will start on first command
        et = exiftool.ExifToolHelper()

        img_files = _get_image_files(img_fileordirpath)
        if not img_files:
            logger.error("No image files found!")
            return

        logger.debug(f"Processing {len(img_files)} file(s)")

        # Use exiftool's native geotag support to update images
        if is_update_images:
            logger.info("Running exiftool with geotag support...")

            # Build geotag parameters
            geotag_params = _build_geotag_params(gpx_filepath, delta_total, is_clear)
            logger.debug(f"Geotag params: {geotag_params}")

            # Execute geotag command using pyexiftool
            try:
                result = et.execute(*geotag_params, *img_files)
                if result:
                    # Log the output from exiftool
                    for line in result.splitlines():
                        if line.strip():
                            logger.info(line)
            except Exception as ex:
                logger.error(f"Error during geotagging: {ex}")

            # Handle update time option - update DateTimeOriginal if requested
            if is_update_time and delta != timedelta(0):
                logger.info("Updating DateTimeOriginal tags...")
                time_params = _build_time_shift_params(delta)
                logger.debug(f"Time shift params: {time_params}")

                try:
                    result = et.execute(*time_params, *img_files)
                    if result:
                        for line in result.splitlines():
                            if line.strip():
                                logger.info(line)
                except Exception as ex:
                    logger.error(f"Error updating time: {ex}")

        # Generate KML output if requested
        if kml_output_path:
            logger.info("Writing KML...")
            _generate_kml_with_exiftool(et, img_files, kml_output_path)

    except UpdateConfirmationAbortedException:
        logger.error("Update aborted by user!")
        sys.exit(0)

    except (KeyboardInterrupt, click.exceptions.Abort) as ex:
        msg = "*** Aborted by user ***"
        if isinstance(ex, click.exceptions.Abort):
            # error is when confirming: logger is on same line so add newline
            msg = "\n" + msg
        logger.error(msg)
        lf = logger.error if not ctx.obj["DEBUG"] else logger.exception
        err_msg = str(ex)
        if err_msg:
            lf(err_msg)
        sys.exit(1)

    except Exception as ex:
        msg = "*** An unrecoverable error occurred ***"
        logger.error(msg)
        lf = logger.error if not ctx.obj["DEBUG"] else logger.exception
        err_msg = str(ex)
        if err_msg:
            lf(err_msg)
        sys.exit(1)

    finally:
        # Close the ExifToolHelper instance at the end
        if et is not None:
            try:
                et.terminate()
            except Exception:
                pass

