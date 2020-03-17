from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
import re
import sys
import traceback

import click
import gpxpy
import gpxpy.gpx
import pandas as pd
import piexif
from termcolor import colored

DEBUG = True

# cf https://gist.github.com/c060604/8a51f8999be12fc2be498e9ca56adc72


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


def get_gps_ifd(lat, lng, altitude=None):
    """
    Adds GPS position as EXIF metadata
    """
    lat_deg = to_deg(lat, ["S", "N"])
    lng_deg = to_deg(lng, ["W", "E"])

    exiv_lat = (
        change_to_rational(lat_deg[0]),
        change_to_rational(lat_deg[1]),
        change_to_rational(lat_deg[2]),
    )
    exiv_lng = (
        change_to_rational(lng_deg[0]),
        change_to_rational(lng_deg[1]),
        change_to_rational(lng_deg[2]),
    )

    gps_ifd = {
        piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: lat_deg[3],
        piexif.GPSIFD.GPSLatitude: exiv_lat,
        piexif.GPSIFD.GPSLongitudeRef: lng_deg[3],
        piexif.GPSIFD.GPSLongitude: exiv_lng,
    }

    if altitude is not None:
        gps_ifd.update(
            {
                piexif.GPSIFD.GPSAltitudeRef: 1,
                piexif.GPSIFD.GPSAltitude: change_to_rational(round(altitude)),
            }
        )

    return gps_ifd


def save_exif_with_gps(file_name, exif_data, gps_ifd):
    exif_data.update({"GPS": gps_ifd})
    exif_bytes = piexif.dump(exif_data)
    piexif.insert(exif_bytes, file_name)


def read_original_photo_time(exif_data, tz_warning=True):
    dt_original = exif_data["Exif"][piexif.ExifIFD.DateTimeOriginal]
    dt_original = dt_original.decode("ascii")
    dt_format = "%Y:%m:%d %H:%M:%S"
    if piexif.ExifIFD.OffsetTimeOriginal in exif_data["Exif"]:
        offset_original = exif_data["Exif"][piexif.ExifIFD.OffsetTimeOriginal]
        offset_original = offset_original.decode("ascii")
        if tz_warning:
            print(colored(f"Found offset in EXIF: {offset_original}", "yellow"))
            tz_warning = True
        # append the offset
        dt_original += offset_original
        dt_format += "%z"
        dt_original = datetime.strptime(dt_original, dt_format)
    else:
        if tz_warning:
            print(
                colored(
                    "No offset in EXIF. Assume UTC. Use --delta to adjust", "yellow"
                )
            )
            tz_warning = True
        dt_original = datetime.strptime(dt_original, dt_format)
        # assume UTC
        dt_original = dt_original.replace(tzinfo=timezone.utc)

    return dt_original


def parse_gpx(gpx_filepath):
    with open(gpx_filepath, "r") as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    df_segments = []
    for track in gpx.tracks:
        for segment in track.segments:
            lats, lngs, times = [], [], []
            for pt in segment.points:
                lats.append(pt.latitude)
                lngs.append(pt.longitude)
                times.append(pt.time)
            d = {"lat": lats, "lng": lngs, "time": times}
            df = pd.DataFrame(d)
            df = df.set_index("time")
            df_segments.append(df)
            print(df.head())

    return df_segments


def parse_timedelta(time_str):
    regex = re.compile(
        r"(?P<negative>-)?(?:(?P<hours>\d+?)hr)?"
        r"(?:(?P<minutes>\d+?)m)?(?:(?P<seconds>\d+?)s)?"
    )
    parts = regex.match(time_str)

    if not parts:
        raise ValueError(f"{time_str} is not a valid time delta expression")

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


@click.command()
@click.argument(
    "gpx_filepath",
    metavar="GPX_FILE",
    type=click.Path(exists=True, resolve_path=True, dir_okay=False),
)
@click.argument(
    "img_filepath",
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
        "drift in the camera compared to the GPS recorder or if a timezone offset "
        "is not set in the EXIF"
    ),
    required=False,
)
@click.option(
    "-t",
    "--tolerance",
    "tolerance",
    help=(
        "Tolerance if time of photo is not inside the time bounds of a GPX segment "
        "(default: 10s)"
    ),
    required=False,
    default="10s",
)
@click.option(
    "-d",
    "--head",
    "is_head",
    is_flag=True,
    help=(
        "Flag to indicate if the tool should just output the times of the first "
        "10 track points in the GPX and the DateTimeOriginal tag of the first "
        "10 images (useful for setting the delta)"
    ),
    required=False,
)
def gpx2exif(gpx_filepath, img_filepath, delta, tolerance, is_head):
    if delta:
        delta = parse_timedelta(delta)
    else:
        # zero
        delta = timedelta(0)

    df_segments = parse_gpx(gpx_filepath)

    if is_head:
        pass

    img_path = Path(img_filepath)

    if img_path.is_file():
        img_path = str(img_path.resolve())
        exif_data = piexif.load(img_path)
        time_original = read_original_photo_time(exif_data)
        time_corrected = time_original + delta
        # TODO process multiple
        df = df_segments[0]
        image_time = pd.Timestamp(time_corrected)
        index = df.index.searchsorted(image_time)
        if index == 0:
            # before first
            pass
        elif index == len(df):
            # after last
            pass
        else:
            # searchsorted returns the index of insertion
            # TODO check if actually present in the index
            # TODO linear interp between before and after if needed
            gps = df.iloc[index - 1]
            print(f"{gps['lat']} {gps['lng']} {gps.name}")
            gps_ifd = get_gps_ifd(gps["lat"], gps["lng"])
            save_exif_with_gps(img_path, exif_data, gps_ifd)

    elif img_path.is_dir():
        pass


def main():
    try:
        gpx2exif()
    except Exception as ex:
        print(colored("*** An unrecoverable error occured ***", "red"))
        print(colored(str(ex), "red"))
        if DEBUG:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
