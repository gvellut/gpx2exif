# gpx2exif

Simple command-line tool to add GPS info from a GPX file to the EXIF tags in images

# Motivation

I use Geopaparazzi on my Android phone to log GPS positions during a walk or hike. The app can export into GPX format, which gives the itinerary, as well as the times for my positions at a relatively high temporal resolution. This is useful for making maps or writing a guide after the fact. I also wanted to make it easier to know the location of the photos taken during the walk and have them show up on the Flickr map. Since my camera doesn't have any GPS logging equipment, I made this tool in order to add the GPS information to the photo EXIF tags based on the GPX tracking points.

# Install

The tool requires Python 3.6+.

To install, launch :

```console
pip install gpx2exif
```

The command above will install the `gpx2exif` Python library and its dependencies. The library includes a command-line script, also named `gpx2exif`, whose functionality is described below.

# Usage

## Options

To get some help about the arguments to the command, just launch with the --help option:

```
Usage: gpx2exif [OPTIONS] GPX_FILE IMAGE_FILE_OR_DIR

Options:
  -d, --delta TEXT      Time shift to apply to the photo Date Time Original
                        EXIF tag to match the date in GPX (see documentation
                        for format). Use if there is a drift in the camera
                        compared to the GPS recorder

  -t, --tolerance TEXT  Tolerance if time of photo is not inside the time
                        bounds of a GPX segment (default: 10s)

  -d, --head            Flag to indicate if the tool should just output the
                        times of the first 10 track points in the GPX and the
                        DateTimeOriginal tag of the first 10 images (useful
                        for setting the delta)

  --help                Show this message and exit.
```

## Examples

### Basic usage

The following command will synch the location data found in the GPX file with a single image, moving forward the time in the image by 2 minutes and 25 seconds:

```console
gpx2exif geopaparazzi_20200315_183754.gpx dsc004239.jpg --delta 2m25s
```

After running this command, the photo will be updated with the location of the closest GPX track point.