from datetime import datetime, timedelta
import logging
import re

import click
from google.cloud import vision
import piexif

from .gpx2exif import read_original_photo_time

logger = logging.getLogger(__name__)


def find_most_likely_date(ref_date, target_time):
    """
    Find the most likely date for a given time, by finding the closest
    occurence of that time to a reference date.
    """
    dt = datetime.combine(ref_date.date(), target_time)
    min_delta = abs(dt - ref_date)
    res = dt.date()
    for day_delta in [-1, 1]:
        new_date = ref_date.date() + timedelta(days=day_delta)
        dt = datetime.combine(new_date, target_time)
        delta = abs(dt - ref_date)
        if delta < min_delta:
            min_delta = delta
            res = new_date
    return res


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
    "--gcp-project",
    "gcp_project",
    help="GCP project to use for the Vision API",
    required=True,
    envvar="GPX2EXIF_GCP_PROJECT",
)
@click.option(
    "--time-diff-only",
    "is_time_diff_only",
    is_flag=True,
    help="Output only the time difference",
    required=False,
)
@click.option(
    "--both-am-pm",
    "is_both_am_pm",
    is_flag=True,
    help="Output both AM and PM possibilities for the time",
    required=False,
)
def extract_time(photo_path, gcp_project, is_time_diff_only, is_both_am_pm):
    # It is not possible to specify a service account key with a single option
    # with the Google Cloud Vision API. The GOOGLE_APPLICATION_CREDENTIALS
    # environment variable must be used.
    exif_data = piexif.load(photo_path)
    # is_ignore_offset=False since we want to have the timezone
    # for comparison later
    time_original = read_original_photo_time(exif_data, is_ignore_offset=False)

    client = vision.ImageAnnotatorClient()

    with open(photo_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    logger.info("Extracting time from photo with Vision API...")
    response = client.text_detection(
        image=image, image_context={"language_hints": ["en"]}
    )
    texts = response.text_annotations
    logger.info("Done")

    if response.error.message:
        raise Exception(
            f"{response.error.message}\nFor more info on error messages, check: "
            "https://cloud.google.com/apis/design/errors"
        )

    time_contenders = []

    for text in texts:
        logger.debug(f'Found "{text.description}"')
        if re.search("^[0-9]+:[0-9]+:[0-9]+$", text.description):
            time_contenders.append(text.description)

    if not time_contenders:
        raise click.ClickException("No time found in photo")

    time_str = time_contenders[0]
    logger.info(f"Found time: {time_str}")

    t = datetime.strptime(time_str, "%H:%M:%S").time()

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

    def process_time(t, time_original):
        date = find_most_likely_date(time_original, t)
        dt = datetime.combine(date, t)
        delta = dt - time_original
        if not is_time_diff_only:
            print(f"Date: {dt.isoformat(timespec='seconds')}Z", end=" ")
        print(f"Delta: {format_timedelta(delta)}")

    if is_both_am_pm:
        t2 = t.replace(hour=(t.hour + 12) % 24)
        process_time(t, time_original)
        process_time(t2, time_original)
    else:
        # choose am or pm based on the exif time
        t2 = t.replace(hour=(t.hour + 12) % 24)
        date = find_most_likely_date(time_original, t)
        dt = datetime.combine(date, t)
        date2 = find_most_likely_date(time_original, t2)
        dt2 = datetime.combine(date2, t2)
        if abs(time_original - dt) < abs(time_original - dt2):
            process_time(t, time_original)
        else:
            process_time(t2, time_original)
