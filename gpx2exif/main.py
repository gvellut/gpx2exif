import logging
import sys

import click
import colorama

from .gpx2exif import gpx2exif
from .gpx2flickr import gpx2flickr

logger = logging.getLogger(__package__)

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


def setup_logging(is_debug):
    global logger
    if is_debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = ColorFormatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@click.group()
@click.option(
    "--debug",
    "is_debug",
    is_flag=True,
    help=("Flag to activate debug mode"),
    required=False,
)
@click.pass_context
def main(ctx, is_debug):
    """ Add location information to images on disk or on Flickr based on a GPX file """
    setup_logging(is_debug)
    # special attribute of context
    ctx.obj = {"DEBUG": is_debug}


gpx2exif = main.command("image")(gpx2exif)
gpx2flickr = main.command("flickr")(gpx2flickr)

if __name__ == "__main__":
    main()
