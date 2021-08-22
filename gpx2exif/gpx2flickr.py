from collections import namedtuple
from datetime import timezone
import logging
import re
import sys

from addict import Dict as Addict
import click
import click_config_file
import dateutil.parser
from flickrapi import FlickrError

from .common import (
    clear_option,
    compute_pos,
    delta_option,
    delta_tz_option,
    kml_option,
    kml_thumbnail_size_option,
    process_deltas,
    process_gpx,
    process_kml,
    process_tolerance,
    tolerance_option,
    update_images_option,
)
from .flickr_api_auth import create_flickr_api

logger = logging.getLogger(__package__)

FlickrAlbum = namedtuple("FlickrAlbum", "album_id url")


def create_photopage_url(image, user):
    return f"https://www.flickr.com/photos/{user.id}/{image.id}"


def parse_album_url(ctx, param, value):
    if value is not None:
        regex = r"flickr\.com/photos/[^/]+/(?:albums|sets)/(\d+)"
        m = re.search(regex, value)
        if m:
            return FlickrAlbum(m.group(1), value)
        else:
            raise click.BadParameter("Not a Flickr album URL", ctx)
    return None


def _get_page_of_images_in_album(flickr, album_id, page, acc, output=False):
    album_info = Addict(
        flickr.photosets.getPhotos(
            photoset_id=album_id, page=page, extras="url_m,date_taken,geo"
        )
    ).photoset

    if output:
        logger.info(
            f"Processing album '{album_info.title}' with {album_info.total} "
            "photos..."
        )

    acc.extend(album_info.photo)

    # return album for data about it
    return album_info


def get_images_in_album(flickr, album):
    flickr_images = []
    page = 1
    while True:
        album_info = _get_page_of_images_in_album(
            flickr, album.album_id, page, flickr_images, output=(page == 1),
        )

        if page >= album_info.pages:
            break
        page += 1

    return flickr_images


def clear_location_from_flickr(flickr, image):
    # only clear if alread georeferenced
    # is 0 if not georeferenced
    if image.latitude:
        flickr.photos.geo.removeLocation(photo_id=image.id)


def set_flickr_location(flickr, image, pos):
    flickr.photos.geo.setLocation(photo_id=image.id, lat=pos[0], lon=pos[1])


def process_image(
    flickr, image, user, gpx_segments, delta, tolerance, is_clear, is_update_images,
):
    time_original = dateutil.parser.isoparse(image.datetaken)
    time_original = time_original.replace(tzinfo=timezone.utc)
    time_corrected = time_original + delta

    image_url = create_photopage_url(image, user)

    logger.debug(f"Processing {image_url}...")
    logger.debug(f"Time corrected {time_corrected.isoformat()}")

    pos = compute_pos(time_corrected, gpx_segments, tolerance)
    if not pos:
        logger.warning(
            f"Cannot compute position for image {image_url} ({time_corrected} "
            f"is outside GPX range + tolerance)"
        )
        if is_clear and is_update_images:
            clear_location_from_flickr(flickr, image)

        return

    logger.debug(f"Pos: {pos}")

    if is_update_images:
        set_flickr_location(flickr, image, pos)

    return pos


def synch_gps_flickr(
    flickr,
    user,
    album,
    gpx_segments,
    delta,
    tolerance,
    is_clear,
    is_update_images,
    is_debug,
):
    images = get_images_in_album(flickr, album)

    logger.warning("Flickr images do not have a timezone! Assumes UTC (+00:00)")

    positions = []
    for image in images:
        try:
            pos = process_image(
                flickr,
                image,
                user,
                gpx_segments,
                delta,
                tolerance,
                is_clear,
                is_update_images,
            )
            if pos:
                positions.append((pos, image))
        except FlickrError:
            msg = f"Image {image.id} could not be processed!"
            lf = logger.error if not is_debug else logger.exception
            lf(msg)

    return positions


DEFAULT_CONFIG_FILENAME = "flickr_api_credentials.txt"
DEFAULT_APP_DIR = "gpx2exif"
DEFAULT_CONFIG_PATH = f"{click.get_app_dir(DEFAULT_APP_DIR)}/{DEFAULT_CONFIG_FILENAME}"

CONFIG_FILE_HELP = (
    f"Path to optional config file for the Flickr API credentials [default :"
    f" {DEFAULT_CONFIG_PATH}]"
)


# TODO support for single image ?
@click.argument(
    "gpx_filepath",
    metavar="GPX_FILE",
    type=click.Path(exists=True, resolve_path=True, dir_okay=False),
)
@click.argument(
    "flickr_album", metavar="FLICKR_ALBUM_URL", callback=parse_album_url,
)
@delta_option
@delta_tz_option
@tolerance_option
@clear_option
@kml_option
@update_images_option
@kml_thumbnail_size_option
@click.option(
    "--api_key",
    "api_key",
    help=("Flickr API key"),
    envvar="FLICKR_API_KEY",
    required=True,
)
@click.option(
    "--api_secret",
    "api_secret",
    help=("Flickr API secret"),
    envvar="FLICKR_API_SECRET",
    required=True,
)
@click_config_file.configuration_option(
    "--config",
    "config_path",
    help=CONFIG_FILE_HELP,
    cmd_name=DEFAULT_APP_DIR,
    config_file_name=DEFAULT_CONFIG_FILENAME,
)
@click.pass_context
def gpx2flickr(
    ctx,
    gpx_filepath,
    flickr_album,
    delta,
    delta_tz,
    tolerance,
    is_clear,
    kml_output_path,
    kml_thumbnail_size,
    is_update_images,
    api_key,
    api_secret,
):
    """ Add location information to Flickr images based on a GPX file """

    try:
        # tz no different from delta for flickr
        _, _, delta_total = process_deltas(delta, delta_tz)

        tolerance = process_tolerance(tolerance)
        gpx_segments = process_gpx(gpx_filepath)

        token_cache_location = click.get_app_dir(DEFAULT_APP_DIR)

        logger.info("Logging in to Flickr...")
        flickr = create_flickr_api(
            api_key, api_secret, token_cache_location=token_cache_location,
        )

        user = Addict(flickr.urls.lookupUser(url=flickr_album.url)).user

        logger.info("Synching Flickr Geo tags to GPX...")
        if not is_update_images:
            logger.warning("The images will not be updated with the positions!")

        positions = synch_gps_flickr(
            flickr,
            user,
            flickr_album,
            gpx_segments,
            delta_total,
            tolerance,
            is_clear,
            is_update_images,
            ctx.obj["DEBUG"],
        )

        def image_src(x):
            return x.url_m

        def image_name(x):
            return create_photopage_url(x, user)

        process_kml(
            positions, kml_output_path, kml_thumbnail_size, image_src, image_name
        )

    except Exception as ex:
        logger.error("*** An unrecoverable error occured ***")
        lf = logger.error if not ctx.obj["DEBUG"] else logger.exception
        lf(str(ex))
        sys.exit(1)
