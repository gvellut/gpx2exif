# gpx2exif

Simple command-line tool to add GPS info from a GPX file to EXIF tags in images

# Motivation

I use [Geopaparazzi](https://www.osgeo.org/projects/geopaparazzi/) on my Android phone to log GPS positions during a walk or hike. The app can export into GPX format, which gives the itinerary, as well as the times for my positions at a relatively high temporal resolution. This is useful for making maps or writing a guide after the fact. I also wanted to make it easier to know the location of the photos taken during the walk and have them show up on the Flickr map. Since my camera doesn't have any GPS logging equipment, I made this tool in order to add the GPS information to the photo EXIF tags based on the GPX tracking points.

# Install

The tool requires Python 3.6+.

To install, launch :

```console
pip install gpx2exif
```

The command above will install the `gpx2exif` Python library and its dependencies. The library includes a command-line script, also named `gpx2exif`, whose functionality is described below.

# Time

## Time EXIF tag in images

The time used for an image is taken from the Date Time Original EXIF metadata tag. In Adobe Bridge, it can be shifted as needed in the UI.

##  Correspondence between time in images and GPX

In the tool, the time in an image is first shifted using the value for the `--delta` switch if present. This switch can be used to correct for the time drift in the camera relative to the GPS logger or correct the time zone (see below). The goal is to align the times in the images with the times in the GPX. The corrected image time is then used to extract a Lat / Lon position from the GPX file (which is essentially a mapping from time to position), which is then added to the EXIF metadata of the image.

There is no switch to shift the time for the GPX file like there is for images: The GPX is assumed to be the reference.

## Time zone

There is no standard time zone tag in EXIF. Some cameras will set the Offset Time Original tag to a time shift (something like "+02:00"), which, by default, is read by the tool in order to set a zone. If this tag is not present, the zone of the times in the images is assumed to be UTC ("+00:00"). In that case, if the times in the images are actually in local time, the `--delta` switch must be used to compensate. The `--ignore-offset` switch can also be used to make the tool ignore the Offset Time Original tag even if present (for instance, if it is wrong).

For example, if the local time is in the "Europe/Paris" time zone aka GMT+1 during winter, it is equivalent to an Offset Time Original of "+01:00". This means that, if the time in the image is 11:15am in local time, it is 10:15am in UTC. If the Offset Time Original is not present (or is ignored), then the `--delta` switch must be set to `-1h` to compensate: The 11:15am found in the EXIF tag is considered to be in UTC but, actually, in UTC, it should be 10:15am so the time shift must be set to *minus* 1 hour.

## Format for time shift and tolerance

The time shift (`--delta` switch) and tolerance (`--tolerance` switch) are time intervals. They can be expressed using a string in a simple format. For example:

```
1h23m54s
```

It is possible to specify only seconds (s) or minutes (m) or hours (h) or any combination but the order (h then m then s) must be kept. No space is allowed.

The time shift can also be negative. For example:

```
-23m
```

# Options

To get some help about the arguments to the command, just launch with the --help option:

```
~$ gpx2exif --help
Usage: gpx2exif [OPTIONS] GPX_FILE IMAGE_FILE_OR_DIR

Options:
  -d, --delta TEXT      Time shift to apply to the photo Date Time Original
                        EXIF tag to match the date in GPX (see documentation
                        for format). Use if there is a drift in the camera
                        compared to the GPS recorder or if an offset is not
                        present in the EXIF. (default: no shift)

  -t, --tolerance TEXT  Tolerance if time of photo is not inside the time
                        range of the GPX track. (default: 10s)

  -o, --ignore-offset   Flag to indicate that the OffsetTimeOriginal should
                        not be used (time of images is assumed UTC). Use
                        --delta to compensate for both timezone and drift.

  -d, --head            Flag to indicate if the tool should just output the
                        times of the first 10 track points in the GPX and the
                        DateTimeOriginal tag of the first 10 images (useful
                        for setting the --delta).

  --help                Show this message and exit.
```

# Examples

### Basic usage

The following command will synch the location data found in the GPX file with a single image, moving forward the time in the image by 2 minutes and 25 seconds:

```console
gpx2exif geopaparazzi_20200315_183754.gpx dsc004239.jpg --delta 2m25s
```

After running this command, the photo will be updated with the location of the GPX track point that is the closest in time.

### Folder

Instead of a single file, it is possible to pass a folder:

```console
gpx2exif geopaparazzi_20200315_183754.gpx photos --delta 2m25s
```