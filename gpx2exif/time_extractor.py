from datetime import datetime, timedelta, timezone
import logging
import os
import re

import click

# Annoying warnings/logs see
# https://github.com/google-ai-edge/mediapipe/issues/5371#issuecomment-3395225750
os.environ["GRPC_VERBOSITY"] = "ERROR"

try:
    from google.cloud import vision

    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

import piexif

from .gpx2exif import read_original_photo_time

logger = logging.getLogger(__name__)


def find_most_likely_datetime(ref_dt, time_str_ambiguous):
    time_obj = datetime.strptime(time_str_ambiguous, "%H:%M:%S").time()
    time1 = time_obj
    time2 = time_obj.replace(hour=(time_obj.hour + 12) % 24)
    candidates = []
    for day_delta in [-1, 0, 1]:
        target_date = ref_dt.date() + timedelta(days=day_delta)
        dt1 = datetime.combine(target_date, time1, tzinfo=timezone.utc)
        candidates.append(dt1)
        dt2 = datetime.combine(target_date, time2, tzinfo=timezone.utc)
        candidates.append(dt2)
    min_delta = float("inf")
    closest_dt = None
    for candidate in candidates:
        delta = abs(candidate - ref_dt)
        if delta.total_seconds() < min_delta:
            min_delta = delta.total_seconds()
            closest_dt = candidate
    return closest_dt


# suitable format for --delta in gpx2exif program
def print_delta(delta):
    logger.info(f"{format_timedelta(delta)}")


def format_time_range(dt_exif, dt_clock):
    """Format time range as HH:MM:SS-HH:MM:SS"""
    time_exif = dt_exif.strftime("%H:%M:%S")
    time_clock = dt_clock.strftime("%H:%M:%S")
    return f"{time_exif}-{time_clock}"


def format_timedelta(td):
    s = ""
    if td.days < 0:
        s += "-"
        td = -td
    seconds = td.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        s += f"{hours}h"
    if minutes > 0:
        s += f"{minutes}m"
    if seconds > 0 or not s:
        s += f"{seconds}s"
    return s


def extract_clock_with_vision_api(photo_path):
    client = vision.ImageAnnotatorClient()

    with open(photo_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    response = client.text_detection(
        image=image, image_context={"language_hints": ["en"]}
    )
    texts = response.text_annotations

    if response.error.message:
        raise Exception(response.error.message)

    time_contenders = []

    for text in texts:
        logger.debug(f'Found "{text.description}"')
        if re.search("^[0-9]+:[0-9]+:[0-9]+$", text.description):
            time_contenders.append(text.description)

    if not time_contenders:
        raise click.ClickException(
            "No time found in photo: Clock must follow %H:%M:%S format"
        )

    time_str_clock = time_contenders[0]
    return time_str_clock


@click.command(
    name="extract-time",
    help="Extract time from a photo and compute a delta with the EXIF time",
)
@click.argument(
    "photo_path",
    metavar="PHOTO_PATH",
    type=click.Path(exists=True, resolve_path=True, dir_okay=False),
)
@click.option(
    "--both-am-pm",
    "is_both_am_pm",
    is_flag=True,
    help="Output both AM and PM possibilities for the time",
    required=False,
)
@click.option(
    "--time-range",
    "is_time_range",
    is_flag=True,
    help="Output time difference as time range (HH:MM:SS-HH:MM:SS) instead of delta",
    required=False,
)
def extract_time(photo_path, is_both_am_pm, is_time_range):
    if not VISION_AVAILABLE:
        raise click.ClickException(
            "Google Cloud Vision is not installed. "
            "Please install the extra: 'vision' eg pip install gpx2exif[vision]"
        )

    exif_data = piexif.load(photo_path)
    # assumes same timezone as the clock read from the image : will set both to UTC
    # in UTC
    dt_exif = read_original_photo_time(
        exif_data, is_ignore_offset=True, tz_warning=False
    )

    logger.info("Extracting time from photo with Vision API...")
    time_str_clock = extract_clock_with_vision_api(photo_path)
    logger.info(f"Found clock time in image: {time_str_clock}")

    logger.info("=====")

    if is_both_am_pm:
        time_clock1 = datetime.strptime(time_str_clock, "%H:%M:%S").time()
        time_clock2 = time_clock1.replace(hour=(time_clock1.hour + 12) % 24)

        # Create datetime objects in UTC (same as EXIF)
        dt_clock1 = datetime.combine(dt_exif.date(), time_clock1, tzinfo=timezone.utc)
        dt_clock2 = datetime.combine(dt_exif.date(), time_clock2, tzinfo=timezone.utc)

        if is_time_range:
            logger.info(format_time_range(dt_exif, dt_clock1))
            logger.info(format_time_range(dt_exif, dt_clock2))
        else:
            delta1 = dt_clock1 - dt_exif
            delta2 = dt_clock2 - dt_exif
            print_delta(delta1)
            print_delta(delta2)
    else:
        dt_clock = find_most_likely_datetime(dt_exif, time_str_clock)

        if is_time_range:
            logger.info(format_time_range(dt_exif, dt_clock))
        else:
            delta = dt_clock - dt_exif
            print_delta(delta)
