from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import subprocess
import sys

import click
import exiftool
import pytz

from .common import (
    UpdateConfirmationAbortedException,
    clear_option,
    compute_pos,
    delta_option,
    delta_tz_option,
    format_timedelta,
    kml_option,
    kml_thumbnail_size_option,
    print_delta,
    process_delta,
    process_gpx,
    process_kml,
    process_tolerance,
    tolerance_option,
    update_images_option,
    update_time_option,
    yes_option,
)

logger = logging.getLogger(__package__)


def image_src(x):
    # issue on Windows if backslash left as is + GE needs a starting /
    if os.name == "nt":
        x = "/" + x.replace("\\", "/")
    return f"file://{x}"


image_name = os.path.basename


def image_style(x):
    """
    Get image style based on orientation.
    Uses exiftool to read orientation instead of piexif.
    """
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata([x])
            if metadata and "EXIF:Orientation" in metadata[0]:
                orientation = metadata[0]["EXIF:Orientation"]
                if orientation == 3:
                    angle = 180
                    origin = "center"
                    translate = ""
                elif orientation == 6:
                    angle = 90
                    origin = "left bottom"
                    translate = "translateY(-100%)"
                elif orientation == 8:
                    angle = -90
                    origin = "top right"
                    translate = "translateX(-100%)"
                else:
                    return ""

                return (
                    f"-webkit-transform: {translate} rotate({angle}deg); "
                    f"-webkit-transform-origin: {origin};"
                )
    except Exception:
        pass
    return ""


def read_original_photo_time(img_path, is_ignore_offset, tz_warning=True):
    """
    Read the original photo time using exiftool.
    """
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata([str(img_path)])
            if not metadata or "EXIF:DateTimeOriginal" not in metadata[0]:
                return None

            dt_original_str = metadata[0]["EXIF:DateTimeOriginal"]
            # ExifTool returns dates in the format "YYYY:MM:DD HH:MM:SS"
            dt_format = "%Y:%m:%d %H:%M:%S"

            if not is_ignore_offset and "EXIF:OffsetTimeOriginal" in metadata[0]:
                offset_original = metadata[0]["EXIF:OffsetTimeOriginal"]
                if tz_warning:
                    logger.warning(f"Found offset in EXIF: {offset_original}")
                # append the offset
                dt_original_str += offset_original
                dt_format += "%z"
                dt_original = datetime.strptime(dt_original_str, dt_format)
            else:
                if tz_warning:
                    if is_ignore_offset:
                        logger.warning("Offset ignored in EXIF. Assume UTC (+00:00)")
                    else:
                        logger.warning("No offset in EXIF. Assume UTC (+00:00)")
                dt_original = datetime.strptime(dt_original_str, dt_format)
                # assume UTC
                dt_original = dt_original.replace(tzinfo=timezone.utc)

            return dt_original
    except Exception as ex:
        logger.error(f"Error reading time from {img_path}: {ex}")
        return None


def collect_image_positions(
    img_fileordirpath,
    gpx_segments,
    delta,
    tolerance,
    is_ignore_offset,
):
    """
    Collect positions for images to generate KML output.
    """
    positions = []
    
    if img_fileordirpath.is_file():
        img_files = [img_fileordirpath]
    elif img_fileordirpath.is_dir():
        img_files = [
            f for f in sorted(img_fileordirpath.iterdir())
            if f.is_file() and not f.name.startswith(".")
        ]
    else:
        return positions

    tz_warning = True
    for img_filepath in img_files:
        try:
            time_original = read_original_photo_time(
                img_filepath, is_ignore_offset, tz_warning
            )
            tz_warning = False
            
            if not time_original:
                logger.warning(
                    f"Cannot compute position for file {img_filepath.name} "
                    "(No DateTimeOriginal tag found)"
                )
                continue

            time_corrected = time_original + delta
            pos = compute_pos(time_corrected, gpx_segments, tolerance)
            
            if not pos:
                logger.warning(
                    f"Cannot compute position for file {img_filepath.name} "
                    f"({time_corrected} is outside GPX range + tolerance)"
                )
                continue

            positions.append((pos, str(img_filepath.resolve())))
            logger.debug(f"{os.path.basename(img_filepath)} => {pos[0]}, {pos[1]}")
        except Exception as ex:
            logger.error(f"File {img_filepath.name} error: {ex}")

    return positions


def synch_gps_exif_with_geotag(
    gpx_filepath,
    img_fileordirpath,
    delta,
    delta_tz,
    is_ignore_offset,
    is_update_time,
):
    """
    Use exiftool's native -geotag option to synchronize GPS data from GPX to images.
    This is the recommended way to use exiftool with GPX files.
    """
    # Build exiftool command
    cmd = ["exiftool"]
    
    # Add the geotag option with the GPX file
    cmd.extend(["-geotag", str(gpx_filepath)])
    
    # Handle time offset for geotag matching
    # The -geotime option allows specifying time offset
    if delta != timedelta(0):
        # Convert timedelta to seconds with sign
        offset_seconds = int(delta.total_seconds())
        if offset_seconds >= 0:
            offset_str = f"+{offset_seconds}"
        else:
            offset_str = str(offset_seconds)
        # Use -geotime to shift the time
        cmd.extend(["-geotime<${DateTimeOriginal}" + offset_str])
    
    # Overwrite original files
    cmd.append("-overwrite_original")
    
    # Add progress output
    cmd.append("-progress")
    
    # Add target files/directory
    if img_fileordirpath.is_file():
        cmd.append(str(img_fileordirpath))
    elif img_fileordirpath.is_dir():
        cmd.append(str(img_fileordirpath))
        # Add extension filter to only process image files
        cmd.extend(["-ext", "jpg", "-ext", "jpeg", "-ext", "JPG", "-ext", "JPEG"])
    
    logger.info("Running exiftool with geotag support...")
    logger.debug(f"Command: {' '.join(cmd)}")
    
    try:
        # Run exiftool
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        
        # Log output
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    logger.info(line)
        
        if result.stderr:
            for line in result.stderr.splitlines():
                if line.strip() and not line.startswith("======"):
                    logger.warning(line)
        
        if result.returncode != 0:
            logger.error(f"exiftool exited with code {result.returncode}")
            return False
        
        # Handle update time option - update DateTimeOriginal if requested
        if is_update_time and delta != timedelta(0):
            logger.info("Updating DateTimeOriginal tags...")
            update_cmd = ["exiftool"]
            
            # Calculate the time shift
            offset_seconds = int(delta.total_seconds())
            if offset_seconds >= 0:
                offset_str = f"+={offset_seconds}"
            else:
                offset_str = f"-={abs(offset_seconds)}"
            
            # Update DateTimeOriginal by shifting it
            update_cmd.extend([
                f"-DateTimeOriginal{offset_str}",
                "-overwrite_original"
            ])
            
            # Add target files/directory
            if img_fileordirpath.is_file():
                update_cmd.append(str(img_fileordirpath))
            elif img_fileordirpath.is_dir():
                update_cmd.append(str(img_fileordirpath))
                update_cmd.extend([
                    "-ext", "jpg", "-ext", "jpeg",
                    "-ext", "JPG", "-ext", "JPEG"
                ])
            
            logger.debug(f"Update time command: {' '.join(update_cmd)}")
            
            update_result = subprocess.run(
                update_cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            
            if update_result.stdout:
                for line in update_result.stdout.splitlines():
                    if line.strip():
                        logger.info(line)
            
            if update_result.returncode != 0:
                logger.error(
                    f"exiftool time update exited with code "
                    f"{update_result.returncode}"
                )
                return False
        
        return True
    except Exception as ex:
        logger.error(f"Error running exiftool: {ex}")
        return False


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
@yes_option
@kml_thumbnail_size_option
@click.pass_context
def exiftool_command(
    ctx,
    gpx_filepath,
    img_fileordirpath,
    delta,
    delta_tz,
    tz,
    tolerance,
    is_ignore_offset,
    is_clear,
    kml_output_path,
    kml_thumbnail_size,
    is_update_images,
    is_update_time,
    is_yes,
):
    """
    Add GPS EXIF tags to local images based on a GPX file using exiftool.
    This is an alternative to the 'image' subcommand that uses the exiftool binary
    with its native -geotag support.
    """
    try:
        if delta_tz and tz:
            raise click.UsageError("Cannot use --delta-tz and --tz at the same time")

        if delta_tz:
            is_ignore_offset = True

        logger.info("Parsing time shift...")
        delta = process_delta(delta)
        print_delta(delta, "Time")

        gpx_segments = process_gpx(gpx_filepath)

        if tz:
            is_ignore_offset = True
            if tz == "auto":
                tz = datetime.now().astimezone().tzinfo
            else:
                try:
                    tz = pytz.timezone(tz)
                except pytz.UnknownTimeZoneError as ex:
                    raise click.UsageError(f"Unknown timezone: {tz}") from ex

            gpx_start_time = gpx_segments[0].iloc[0].name.replace(tzinfo=None)
            gpx_end_time = gpx_segments[-1].iloc[-1].name.replace(tzinfo=None)

            start_offset = tz.utcoffset(gpx_start_time)
            end_offset = tz.utcoffset(gpx_end_time)

            if start_offset != end_offset:
                logger.warning(
                    "Timezone offset is different between the start and end of the "
                    f"GPX track: {start_offset} vs {end_offset}. Using the start "
                    "offset."
                )

            delta_tz = -start_offset
        elif delta_tz:
            delta_tz = process_delta([delta_tz])
        else:
            delta_tz = None

        if delta_tz:
            print_delta(delta_tz, "TZ time")
            delta_total = delta + delta_tz
            print_delta(delta_total, "Total time")
        else:
            delta_total = delta

        tolerance = process_tolerance(tolerance)
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

        # Use exiftool's native geotag support to update images
        if is_update_images:
            success = synch_gps_exif_with_geotag(
                gpx_filepath,
                img_fileordirpath,
                delta_total,
                delta_tz,
                is_ignore_offset,
                is_update_time,
            )
            if not success:
                logger.error("Failed to update images with exiftool")

        # Collect positions for KML output
        positions = []
        if kml_output_path:
            positions = collect_image_positions(
                img_fileordirpath,
                gpx_segments,
                delta_total,
                tolerance,
                is_ignore_offset,
            )

        process_kml(
            positions,
            kml_output_path,
            kml_thumbnail_size,
            image_src,
            image_name,
            image_style,
        )

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

