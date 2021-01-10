from datetime import datetime, timedelta, timezone
from fractions import Fraction
import logging
import os
from pathlib import Path
import re
import sys

import click
import colorama
import gpxpy
import gpxpy.gpx
import pandas as pd
import piexif
from termcolor import colored

DEBUG = True

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


def _save_exif(file_path_s, exif_data):
    exif_bytes = piexif.dump(exif_data)
    piexif.insert(exif_bytes, file_path_s)


def save_exif_with_gps(file_path_s, exif_data, gps_ifd):
    exif_data.update({"GPS": gps_ifd})
    _save_exif(file_path_s, exif_data)


def clear_gps_from_exif(file_path_s, exif_data):
    del exif_data["GPS"]
    _save_exif(file_path_s, exif_data)


def compute_pos(img_time, gpx_segments, tolerance):
    img_time = pd.Timestamp(img_time)
    tolerance = pd.Timedelta(tolerance)
    for df in gpx_segments:
        if img_time in df.index:
            gps = df.loc[img_time]
            return gps["lat"], gps["lon"]

        # searchsorted returns the index for insertion to keep the
        # series sorted with the arg value inserted
        index = df.index.searchsorted(img_time)
        if index == 0:
            # before first
            dt = df.index[0].tz_convert("utc") - img_time.tz_convert("utc")
            if dt < tolerance:
                # consider the first row as the value
                gps = df.iloc[0]
                return gps["lat"], gps["lon"]
            else:
                # no suitable point in GPX found
                return None
        elif index == len(df):
            # after last
            dt = img_time.tz_convert("utc") - df.index[-1].tz_convert("utc")
            if dt < tolerance:
                # consider the last row as the value
                # TODO search the next segment to see if closer ?
                gps = df.iloc[-1]
                return gps["lat"], gps["lon"]
            else:
                # search next segment
                continue
        else:
            gps_before = df.iloc[index - 1]
            gps_after = df.iloc[index]
            gpx_gap = gps_after.name - gps_before.name
            img_gap = img_time.tz_convert("utc") - gps_before.name.tz_convert("utc")
            gap_ratio = img_gap / gpx_gap
            # linear interp
            lat = gps_before["lat"] + (gps_after["lat"] - gps_before["lat"]) * gap_ratio
            lon = gps_before["lon"] + (gps_after["lon"] - gps_before["lon"]) * gap_ratio
            return lat, lon

    return None


def process_head(
    img_fileordirpath, gpx_segments, delta, is_ignore_offset, head_limit=10
):
    counter = 0
    for df in gpx_segments:
        for value in df.index:
            logger.info(f"{counter + 1:02d} - GPX Time: {value}")
            counter += 1
            if counter == head_limit:
                break
        else:
            continue
        break

    if img_fileordirpath.is_file():
        head_image(1, img_fileordirpath, delta, is_ignore_offset)
    elif img_fileordirpath.is_dir():
        counter = 0
        tz_warning = True
        for img_filepath in sorted(img_fileordirpath.iterdir()):
            try:
                head_image(
                    counter + 1, img_filepath, delta, is_ignore_offset, tz_warning
                )
                tz_warning = False
                counter += 1
                if counter == head_limit:
                    break
            except piexif.InvalidImageDataError:
                pass


def head_image(index, img_path, delta, is_ignore_offset, tz_warning=True):
    exif_data = piexif.load(str(img_path.resolve()))
    time_original = read_original_photo_time(exif_data, is_ignore_offset, tz_warning)
    time_corrected = time_original + delta

    logger.info(
        f"{index:02d} - Date Time Original (corrected): {time_corrected.isoformat()} "
        f"[{img_path.name}]"
    )


def process_image(
    img_path,
    gpx_segments,
    delta,
    tolerance,
    is_ignore_offset,
    is_clear,
    tz_warning=True,
):
    img_path_s = str(img_path.resolve())
    exif_data = piexif.load(str(img_path.resolve()))
    time_original = read_original_photo_time(exif_data, is_ignore_offset, tz_warning)
    time_corrected = time_original + delta

    logger.debug(f"Time corrected {time_corrected.isoformat()}")

    pos = compute_pos(time_corrected, gpx_segments, tolerance)
    if not pos:
        logger.warning(
            f"Cannot compute position for file {img_path.name} ({time_corrected} "
            f"is outside GPX range + tolerance)"
        )
        if is_clear:
            clear_gps_from_exif(img_path_s, exif_data)

        return

    lat, lon = pos

    logger.debug(f"{os.path.basename(img_path)} => {lat}, {lon}")

    gps_ifd = get_gps_ifd(lat, lon)
    save_exif_with_gps(img_path_s, exif_data, gps_ifd)
    return


def read_original_photo_time(exif_data, is_ignore_offset, tz_warning=True):
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
            logger.warning("No offset in EXIF. Assume UTC (+00:00)")
        dt_original = datetime.strptime(dt_original, dt_format)
        # assume UTC
        dt_original = dt_original.replace(tzinfo=timezone.utc)

    return dt_original


def read_gpx(gpx_filepath):
    with open(gpx_filepath, "r") as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    df_segments = []
    for track in gpx.tracks:
        for segment in track.segments:
            lats, lons, times = [], [], []
            for pt in segment.points:
                # TODO get elevation ?
                lats.append(pt.latitude)
                lons.append(pt.longitude)
                times.append(pt.time)
            d = {"lat": lats, "lon": lons, "time": times}
            df = pd.DataFrame(d)
            df = df.set_index("time")
            df_segments.append(df)

    return df_segments


def parse_timedelta(time_str):
    regex = re.compile(
        r"(?P<negative>-)?(?:(?P<hours>\d+?)h)?"
        r"(?:(?P<minutes>\d+?)m)?(?:(?P<seconds>\d+?)s)?"
    )
    parts = regex.match(time_str)

    if not time_str or not parts:
        raise ValueError(f"'{time_str}' is not a valid time delta expression")

    parts = parts.groupdict()
    time_params = {}

    if parts.get("negative", None) is not None:
        del parts["negative"]
        mult = -1
    else:
        mult = 1

    for (name, param) in parts.items():
        if param:
            time_params[name] = mult * int(param)

    return timedelta(**time_params)


# specify colors for different logging levels
LOG_COLORS = {logging.ERROR: colorama.Fore.RED, logging.WARNING: colorama.Fore.YELLOW}


class ColorFormatter(logging.Formatter):
    def format(self, record, *args, **kwargs):
        if record.levelno in LOG_COLORS:
            record.msg = "{color_begin}{message}{color_end}".format(
                message=record.msg,
                color_begin=LOG_COLORS[record.levelno],
                color_end=colorama.Style.RESET_ALL,
            )
        return super().format(record, *args, **kwargs)


def setup_logging():
    global logger
    if DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = ColorFormatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@click.command()
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
@click.option(
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
@click.option(
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
@click.option(
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
@click.option(
    "-c",
    "--clear",
    "is_clear",
    is_flag=True,
    help=(
        "Flag to indicate that the GPX EXIF fields should be cleared if no position "
        "can be computed for the photo."
    ),
    required=False,
)
def gpx2exif(
    gpx_filepath,
    img_fileordirpath,
    delta,
    tolerance,
    is_ignore_offset,
    is_head,
    is_clear,
):
    if delta:
        logger.info("Parsing time shift...")
        delta = parse_timedelta(delta)
    else:
        delta = timedelta(0)
    logger.info(colored(f"Time shift: {int(delta.total_seconds())}s", "green"))

    if tolerance:
        logger.info("Parsing tolerance...")
        # in case negative
        tolerance = timedelta(seconds=abs(parse_timedelta(tolerance).total_seconds()))
    else:
        tolerance = timedelta(seconds=10)
    logger.info(colored(f"Tolerance: {int(tolerance.total_seconds())}s", "green"))

    logger.info("Parsing GPX...")
    gpx_segments = read_gpx(gpx_filepath)
    logger.info(
        f"GPX time range: {gpx_segments[0].iloc[0].name} => "
        f"{gpx_segments[-1].iloc[0-1].name}"
    )

    img_fileordirpath = Path(img_fileordirpath)

    if is_head:
        logger.info("Head...")
        process_head(img_fileordirpath, gpx_segments, delta, is_ignore_offset)
        return

    logger.info("Synching EXIF GPS to GPX...")
    if img_fileordirpath.is_file():
        process_image(
            img_fileordirpath,
            gpx_segments,
            delta,
            tolerance,
            is_ignore_offset,
            is_clear,
        )
    elif img_fileordirpath.is_dir():
        tz_warning = True
        for img_filepath in sorted(img_fileordirpath.iterdir()):
            # do not process hidden files (sometimes used by the OS to store
            # metadata, like .DS_store on macOS)
            if img_filepath.is_file() and not img_filepath.name.startswith("."):
                try:
                    process_image(
                        img_filepath,
                        gpx_segments,
                        delta,
                        tolerance,
                        is_ignore_offset,
                        is_clear,
                        tz_warning,
                    )
                    tz_warning = False
                except piexif.InvalidImageDataError:
                    logger.error(
                        f"File {img_filepath.name} is not a JPEG or TIFF image"
                    )


def main():
    setup_logging()
    try:
        gpx2exif()
    except Exception as ex:
        logger.error("*** An unrecoverable error occured ***")
        lf = logger.error if not DEBUG else logger.exception
        lf(str(ex))
        sys.exit(1)


if __name__ == "__main__":
    main()
