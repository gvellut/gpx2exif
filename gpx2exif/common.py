from datetime import timedelta
import logging
import re

import click
import gpxpy
import gpxpy.gpx
import pandas as pd
import simplekml
from termcolor import colored

logger = logging.getLogger(__package__)

delta_option = click.option(
    "-d",
    "--delta",
    "delta",
    help=(
        "Time shift to apply to the photo times "
        "to match the date in GPX (see documentation for format). "
        "Multiple possible."
        "[default: no shift]"
    ),
    required=False,
    multiple=True,
)

delta_tz_option = click.option(
    "-d",
    "--delta-tz",
    "delta_tz",
    help=(
        "Time zone offset to apply to the photo times "
        "to match the date in GPX (see documentation for format). "
        "If present, assumes --ignore-offset. "
        "[default: no shift (timezone of the image if present)]"
    ),
    required=False,
)

tolerance_option = click.option(
    "-t",
    "--tolerance",
    "tolerance",
    help=(
        "Tolerance if time of the photo is not inside the time range of the GPX track. "
        "(default: 10s)"
    ),
    required=False,
    default="10s",
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
        "Flag to indicate that the times of the photos should be cleared if no "
        "position can be computed."
    ),
    required=False,
)

update_time_option = click.option(
    "-u",
    "--update-time/--no-update-time",
    "is_update_time",
    default=False,
    help=(
        "Flag to indicate that the times of the photos should be updated according to "
        "the delta."
    ),
    required=False,
)


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


def format_timedelta(td):
    if td < timedelta(0):
        return "-" + format_timedelta(-td)
    else:
        s = int(td.total_seconds())
        hours, remainder = divmod(s, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h{minutes}m{seconds}s"


def process_delta(deltas):
    if deltas:
        logger.info("Parsing time shift...")
        delta = timedelta(0)
        for delta_s in deltas:
            delta += parse_timedelta(delta_s)
    else:
        delta = timedelta(0)

    return delta


def process_deltas(delta, delta_tz):
    delta = process_delta(delta)
    _print_delta(delta)

    if delta_tz:
        delta_tz = process_delta([delta_tz])
        _print_delta(delta_tz, "TZ time")

        delta_total = delta + delta_tz
        _print_delta(delta_total, "Total time")
    else:
        delta_total = delta

    return delta, delta_tz, delta_total


def _print_delta(delta, delta_type="Time"):
    delta_s = format_timedelta(delta)
    logger.info(colored(f"{delta_type} shift: {delta_s}", "green"))


def process_tolerance(tolerance):
    if tolerance:
        logger.info("Parsing tolerance...")
        # in case negative
        tolerance = timedelta(seconds=abs(parse_timedelta(tolerance).total_seconds()))
    else:
        tolerance = timedelta(seconds=10)
    logger.info(colored(f"Tolerance: {int(tolerance.total_seconds())}s", "green"))
    return tolerance


def process_gpx(gpx_filepath):
    logger.info("Parsing GPX...")
    gpx_segments = read_gpx(gpx_filepath)
    logger.info(
        f"GPX time range: {gpx_segments[0].iloc[0].name} => "
        f"{gpx_segments[-1].iloc[0-1].name}"
    )
    return gpx_segments


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


def process_kml(positions, kml_output_path, kml_thumbnail_size, image_src, image_name):
    if kml_output_path:
        logger.info("Writing KML...")
        if len(positions) > 0:
            write_kml(
                positions, kml_output_path, kml_thumbnail_size, image_src, image_name
            )
        else:
            logger.warning("No KML output (no georeferenced photos)!")


def write_kml(positions, kml_path, kml_thumbnail_size, image_src, image_name):
    kml = simplekml.Kml()
    sharedstyle = simplekml.Style()
    sharedstyle.balloonstyle.text = "$[description]"
    for latlon, image in positions:
        desc = f"""<![CDATA[
 <img src="{image_src(image)}" width="{kml_thumbnail_size}" /><br/><br/>
 {image_name(image)}<br/>
 ]]>"""
        pnt = kml.newpoint(description=desc, coords=[latlon[::-1]])
        pnt.style = sharedstyle
    try:
        kml.save(kml_path)
    except Exception:
        logger.exception(f"Unable to save KML to {kml_path}")
