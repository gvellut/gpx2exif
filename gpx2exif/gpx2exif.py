from datetime import datetime, timezone
from fractions import Fraction
import logging
import os
from pathlib import Path
import sys

import click
import piexif

from .common import (
    clear_option,
    compute_pos,
    delta_option,
    delta_tz_option,
    format_timedelta,
    kml_option,
    kml_thumbnail_size_option,
    process_deltas,
    process_gpx,
    process_kml,
    process_tolerance,
    tolerance_option,
    update_images_option,
    update_time_option,
)

logger = logging.getLogger(__package__)


# code for GPS EXIF https://gist.github.com/c060604/8a51f8999be12fc2be498e9ca56adc72


def to_deg(value, loc):
    """
    Converts decimal coordinates into degrees, minutes and seconds tuple
    value is float gps-value, loc is direction list ["S", "N"] or ["W", "E"]
    return: tuple like (25, 13, 48.343 ,'N')
    """
    if value < 0:
        loc_value = loc[0]
    elif value > 0:
        loc_value = loc[1]
    else:
        loc_value = ""
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min = int(t1)
    sec = round((t1 - min) * 60, 5)
    return (deg, min, sec, loc_value)


def change_to_rational(number):
    """
    Converts a number to rationnal
    return: tuple like (1, 2), (numerator, denominator)
    """
    f = Fraction(str(number))
    return (f.numerator, f.denominator)


def get_gps_ifd(lat, lon, altitude=None):
    """
    Returns GPS structure of EXIF metadata
    """
    lat_deg = to_deg(lat, ["S", "N"])
    lon_deg = to_deg(lon, ["W", "E"])

    exiv_lat = (
        change_to_rational(lat_deg[0]),
        change_to_rational(lat_deg[1]),
        change_to_rational(lat_deg[2]),
    )
    exiv_lon = (
        change_to_rational(lon_deg[0]),
        change_to_rational(lon_deg[1]),
        change_to_rational(lon_deg[2]),
    )

    gps_ifd = {
        piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: lat_deg[3],
        piexif.GPSIFD.GPSLatitude: exiv_lat,
        piexif.GPSIFD.GPSLongitudeRef: lon_deg[3],
        piexif.GPSIFD.GPSLongitude: exiv_lon,
    }

    if altitude is not None:
        gps_ifd.update(
            {
                piexif.GPSIFD.GPSAltitudeRef: 1,
                piexif.GPSIFD.GPSAltitude: change_to_rational(round(altitude)),
            }
        )

    return gps_ifd


def flush_exif(file_path_s, exif_data):
    exif_bytes = piexif.dump(exif_data)
    piexif.insert(exif_bytes, file_path_s)


def save_exif_with_gps(exif_data, gps_ifd):
    exif_data.update({"GPS": gps_ifd})
    return True


def clear_gps_from_exif(exif_data):
    if exif_data.get("GPS"):
        del exif_data["GPS"]
        return True
    return False


# TODO simplify parameters => struct
def process_image(
    img_path,
    gpx_segments,
    delta,
    delta_tz,
    tolerance,
    is_ignore_offset,
    is_clear,
    is_update_images,
    is_update_time,
    tz_warning=True,
):
    img_path_s = str(img_path.resolve())
    exif_data = piexif.load(str(img_path.resolve()))
    time_original = read_original_photo_time(exif_data, is_ignore_offset, tz_warning)

    to_flush = False

    if not time_original:
        logger.warning(
            f"Cannot compute position for file {img_path.name} "
            "(No DateTimeOriginal tag found)"
        )
        if is_update_images and is_clear:
            to_flush = clear_gps_from_exif(exif_data) or to_flush

        if to_flush:
            flush_exif(img_path_s, exif_data)
        return None

    time_corrected = time_original + delta

    logger.debug(f"Time corrected {time_corrected.isoformat()}")

    if is_update_images and is_update_time:
        update_original_photo_time(
            exif_data, time_corrected, delta_tz, is_ignore_offset
        )
        to_flush = True

    pos = compute_pos(time_corrected, gpx_segments, tolerance)
    if not pos:
        logger.warning(
            f"Cannot compute position for file {img_path.name} ({time_corrected} "
            f"is outside GPX range + tolerance)"
        )
        if is_update_images and is_clear:
            to_flush = clear_gps_from_exif(exif_data) or to_flush

        if to_flush:
            flush_exif(img_path_s, exif_data)
        return None

    lat, lon = pos

    logger.debug(f"{os.path.basename(img_path)} => {lat}, {lon}")

    if is_update_images:
        gps_ifd = get_gps_ifd(lat, lon)
        save_exif_with_gps(exif_data, gps_ifd)
        to_flush = True

    if to_flush:
        flush_exif(img_path_s, exif_data)
    return pos


def read_original_photo_time(exif_data, is_ignore_offset, tz_warning=True):
    if piexif.ExifIFD.DateTimeOriginal not in exif_data["Exif"]:
        return None

    dt_original = exif_data["Exif"][piexif.ExifIFD.DateTimeOriginal]
    dt_original = dt_original.decode("ascii")
    dt_format = "%Y:%m:%d %H:%M:%S"
    if not is_ignore_offset and piexif.ExifIFD.OffsetTimeOriginal in exif_data["Exif"]:
        offset_original = exif_data["Exif"][piexif.ExifIFD.OffsetTimeOriginal]
        offset_original = offset_original.decode("ascii")
        if tz_warning:
            logger.warning(f"Found offset in EXIF: {offset_original}")
        # append the offset
        dt_original += offset_original
        dt_format += "%z"
        dt_original = datetime.strptime(dt_original, dt_format)
    else:
        if tz_warning:
            if is_ignore_offset:
                logger.warning("Offset ignored in EXIF. Assume UTC (+00:00)")
            else:
                logger.warning("No offset in EXIF. Assume UTC (+00:00)")
        dt_original = datetime.strptime(dt_original, dt_format)
        # assume UTC
        dt_original = dt_original.replace(tzinfo=timezone.utc)

    return dt_original


def update_original_photo_time(exif_data, dt, delta_tz, is_ignore_offset):
    dt_format = "%Y:%m:%d %H:%M:%S"

    if delta_tz:
        # the delta_tz transforms from local time to UTC and has been added
        # to the delta already
        # to stay in local time, substract it
        dt -= delta_tz

    # if Time Offset present in original photo, the dt is a datetime with
    # timezone and strftime will print the local time part
    # if not, it is in local time anyway
    dt_original = datetime.strftime(dt, dt_format)
    exif_data["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_original.encode("ascii")

    if is_ignore_offset:
        # TODO other option would be to set it to delta_tz
        # delete if present
        if piexif.ExifIFD.OffsetTimeOriginal in exif_data["Exif"]:
            del exif_data["Exif"][piexif.ExifIFD.OffsetTimeOriginal]


def synch_gps_exif(
    img_fileordirpath,
    gpx_segments,
    delta,
    delta_tz,
    tolerance,
    is_ignore_offset,
    is_clear,
    is_update_images,
    is_update_time,
):
    if img_fileordirpath.is_file():
        positions = []
        pos = process_image(
            img_fileordirpath,
            gpx_segments,
            delta,
            delta_tz,
            tolerance,
            is_ignore_offset,
            is_clear,
            is_update_images,
            is_update_time,
        )
        if pos:
            positions.append((pos, str(img_fileordirpath.resolve())))
        return positions
    elif img_fileordirpath.is_dir():
        tz_warning = True
        positions = []
        for img_filepath in sorted(img_fileordirpath.iterdir()):
            # do not process hidden files (sometimes used by the OS to store
            # metadata, like .DS_store on macOS)
            if img_filepath.is_file() and not img_filepath.name.startswith("."):
                try:
                    pos = process_image(
                        img_filepath,
                        gpx_segments,
                        delta,
                        delta_tz,
                        tolerance,
                        is_ignore_offset,
                        is_clear,
                        is_update_images,
                        is_update_time,
                        tz_warning,
                    )
                    # TODO ensure TZ Warning has really been output
                    tz_warning = False
                    if pos:
                        positions.append((pos, str(img_filepath.resolve())))
                except piexif.InvalidImageDataError:
                    logger.error(
                        f"File {img_filepath.name} is not a JPEG or TIFF image"
                    )

        return positions


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
@tolerance_option
@click.option(
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
@clear_option
@kml_option
@update_images_option
@update_time_option
@kml_thumbnail_size_option
@click.pass_context
def gpx2exif(
    ctx,
    gpx_filepath,
    img_fileordirpath,
    delta,
    delta_tz,
    tolerance,
    is_ignore_offset,
    is_clear,
    kml_output_path,
    kml_thumbnail_size,
    is_update_images,
    is_update_time,
):
    """ Add GPS EXIF tags to local images based on a GPX file """
    try:
        if delta_tz:
            is_ignore_offset = True

        delta, delta_tz, delta_total = process_deltas(delta, delta_tz)

        tolerance = process_tolerance(tolerance)
        gpx_segments = process_gpx(gpx_filepath)

        img_fileordirpath = Path(img_fileordirpath)

        logger.info("Synching EXIF GPS to GPX...")
        if not is_update_images:
            logger.warning("The images will not be updated!")

        if is_update_images and is_update_time:
            fdt = format_timedelta(delta)
            logger.warning(f"The times in the images will be shifted: {fdt}!")

        positions = synch_gps_exif(
            img_fileordirpath,
            gpx_segments,
            delta_total,
            delta_tz,
            tolerance,
            is_ignore_offset,
            is_clear,
            is_update_images,
            is_update_time,
        )

        def image_src(x):
            # issue on Windows if backslash left as is + GE needs a starting /
            if os.name == "nt":
                x = "/" + x.replace("\\", "/")
            return f"file://{x}"

        image_name = os.path.basename
        process_kml(
            positions, kml_output_path, kml_thumbnail_size, image_src, image_name
        )

    except Exception as ex:
        logger.error("*** An unrecoverable error occured ***")
        lf = logger.error if not ctx.obj["DEBUG"] else logger.exception
        lf(str(ex))
        sys.exit(1)
