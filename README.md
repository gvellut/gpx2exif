# gpx2exif

Simple command-line tool to add GPS info from a GPX file to EXIF tags in local images or to images hosted on Flickr

# Motivation

I use [Geopaparazzi](https://www.osgeo.org/projects/geopaparazzi/) on my Android phone to log GPS positions during a walk or hike. The app can export into GPX format, which gives the itinerary, as well as the times for my positions at a relatively high temporal resolution. This is useful for making maps or writing a guide after the fact. I also wanted to make it easier to know the location of the photos taken during the walk and have them show up on the Flickr map. Since my camera doesn't have any GPS logging equipment, I made this tool in order to add the GPS information to the photo EXIF tags based on the GPX tracking points. 

I also had some GPX recordings corresponding to Flickr images that I had uploaded before I made this tool, so I have also added a way to set the location of existing Flickr images based on a GPX file.

# Install

The tool requires Python 3.6+.

To install, launch :

```console
pip install gpx2exif
```

The command above will install the `gpx2exif` Python library and its dependencies. The library includes a command-line script, also named `gpx2exif`, whose functionality is described below.

# Time

##  Correspondence between time in images and GPX

In the tool, the time in an image is first shifted using the value for the `--delta` option if present. This option can be used to correct for the time drift in the camera relative to the GPS logger or correct the time zone (in the latter case the `--delta-tz` option is preferred; See below). The goal is to align the times in the images with the times in the GPX, assumed to be in __UTC__. The corrected image time is then used to extract a Lat / Lon position from the GPX file (which is essentially a mapping from time to position), which is then added to the EXIF metadata of the image.

There is no switch to shift the time for the GPX file like there is for images: The GPX is assumed to be the reference.


## EXIF image time

### Time EXIF tag

The time used for an image is taken from the __Date Time Original__ EXIF metadata tag. In Adobe Bridge, it can be shifted as needed in the UI. It can be also shifted using the `--delta` and `--delta-tz` options using `gpx2exif`.

### Time zone

There is no standard time zone tag in EXIF. Some cameras will set the __Offset Time Original__ tag to a time shift (something like "+02:00"), which, by default, is read by the tool in order to set a zone. If this tag is not present, the zone of the times in the images is assumed to be UTC ("+00:00"). In that case, if the times in the images are actually in local time, the `--delta-tz` option must be used to compensate. The `--ignore-offset` switch can also be used to make the tool ignore the Offset Time Original tag even if present (for instance, if it is wrong).

For example, if the local time is in the "Europe/Paris" time zone aka GMT+1 during winter, it is equivalent to an Offset Time Original of "+01:00". This means that, if the time in the image is 11:15am in local time, it is 10:15am in UTC. If the Offset Time Original is not present (or is ignored), then the `--delta-tz` option must be set to `-1h` to compensate: The 11:15am found in the EXIF tag is considered to be in UTC but, actually, in UTC, it should be 10:15am so the time shift must be set to *minus* 1 hour. However, if the Offset Time Original is present and set to "+01:00", `gpx2exif` will set the delta automatically (by default) to `-1h`.

#### Drift and time zone shifts

 If both `--delta-tz` and `--delta` are present, they are added together to obtain the shift for conversion to UTC.
 
 They are basically interchangeable except in the case when the `--update-time` switch is used: In that case, if both options are present, the times in the images will be updated only using the value of the `--delta` option. The reason is that it is assumed that the times in the images should be in local time, whereas the addition of `--delta-tz` and `--delta` result in a time in UTC: The `--delta-tz` sets the timezone and the `--delta` corrects the drift.

## Flickr image time

### Time attribute

The time used for a Flickr image is the __Date Taken__ attribute from the Flickr API. Usually it corresponds to the __Date Time Original__ of the EXIF tag of the original photo but it can also be updated manually through the UI (Organizr).

### Time zone

There is no timezone for the __Date Taken__ attribute on Flickr and therefore the time is asssumed to be UTC (just like when the offset is missing from the EXIF tags for images on disk). Use the `--delta` or `-delta-tz` option to compensate (see above).

## Format for time shift and tolerance

The time shift (`--delta` switch) and tolerance (`--tolerance` switch) are time intervals. They can be expressed using a string in a simple format. For example:

```
1h23m54s
```

It is possible to specify only seconds (s) or minutes (m) or hours (h) or any combination but the order (h then m then s) must be kept. No space is allowed.

The `--delta` switch can be present multiple times. For example, one to set the time zone and that will not change (or very infrequently, like on DST switch days) between runs of `gpx2exif` and one set to the time drift of the camera, which can change often (additional 5 to 10 seconds of drift every session with my Fujifilm camera). `gpx2exif` will add the two together to compute a single delta for the run.

The time shift can also be negative. For example:

```
-23m
```

# Options

To get some help about the arguments to the command, just launch with the --help option:

```
~$ gpx2exif --help
Usage: gpx2exif [OPTIONS] COMMAND [ARGS]...

  Add location information to images on disk or on Flickr based on a GPX file

Options:
  --debug   Flag to activate debug mode
  --help    Show this message and exit.

Commands:
  flickr
  image
```

## image subcommand

The image subcommand allows to synch a GPX file with an image file or a folder of image files on a local disk :

```
~$ gpx2exif image --help
Usage: gpx2exif image [OPTIONS] GPX_FILE IMAGE_FILE_OR_DIR

  Add GPS EXIF tags to local images based on a GPX file

Options:
  -d, --delta TEXT                Time shift to apply to the photo times to
                                  match the date in GPX (see documentation for
                                  format). Multiple possible.[default: no
                                  shift]

  -d, --delta-tz TEXT             Time zone offset to apply to the photo times
                                  to match the date in GPX (see documentation
                                  for format). If present, assumes --ignore-
                                  offset. [default: no shift (timezone of the
                                  image if present)]

  -t, --tolerance TEXT            Tolerance if time of the photo is not inside
                                  the time range of the GPX track. (default:
                                  10s)

  -o, --ignore-offset             Flag to indicate that the OffsetTimeOriginal
                                  should not be used (time of images is
                                  assumed UTC). Use --delta to compensate for
                                  both timezone and drift.

  -c, --clear                     Flag to indicate that the times of the
                                  photos should be cleared if no position can
                                  be computed.

  -k, --kml TEXT                  Path for a KML output file with placemarks
                                  for the photos (useful for checking the
                                  delta)

  --update-images / --no-update-images
                                  Flag to indicate that the images should not
                                  be udpated and only a KML will generated

  -u, --update-time / --no-update-time
                                  Flag to indicate that the times of the
                                  photos should be updated according to the
                                  delta.

  --kml_thumbnail_size INTEGER    Pixel size of the image popup in the KML
  --help                          Show this message and exit.
```

## flickr subcommand

```
~$ gpx2exif flickr --help
Usage: gpx2exif flickr [OPTIONS] GPX_FILE FLICKR_ALBUM_URL

  Add location information to Flickr images based on a GPX file

Options:
  -d, --delta TEXT                Time shift to apply to the photo times to
                                  match the date in GPX (see documentation for
                                  format). Multiple possible.[default: no
                                  shift]

  -d, --delta-tz TEXT             Time zone offset to apply to the photo times
                                  to match the date in GPX (see documentation
                                  for format). If present, assumes --ignore-
                                  offset. [default: no shift (timezone of the
                                  image if present)]

  -t, --tolerance TEXT            Tolerance if time of the photo is not inside
                                  the time range of the GPX track. (default:
                                  10s)

  -c, --clear                     Flag to indicate that the times of the
                                  photos should be cleared if no position can
                                  be computed.

  -k, --kml TEXT                  Path for a KML output file with placemarks
                                  for the photos (useful for checking the
                                  delta)

  --update-images / --no-update-images
                                  Flag to indicate that the images should not
                                  be udpated and only a KML will generated

  --kml_thumbnail_size INTEGER    Pixel size of the image popup in the KML
  --api_key TEXT                  Flickr API key  [required]
  --api_secret TEXT               Flickr API secret  [required]
  --config FILE                   Path to optional config file for the Flickr
                                  API credentials [default :
                                  /Users/guilhem/Library/Application
                                  Support/gpx2exif/flickr_api_credentials.txt]

  --help                          Show this message and exit.
```

### Flickr API permision

- The API keys and secrets can be obtained by registering a non-commercial application with Flickr at https://www.flickr.com/services/api/misc.api_keys.html Since the API has limits on how many calls can be made per hour, I cannot share my own key.
- A config file is optional and, if present, can contain values for the `api_key` and `api_secret` arguments. It should be a text file with the content like this:
```
api_key="<Flickr API Key>"
api_secret="<Flickr API Secret>"
```
(the quotes should be present)
- The default location depends on the OS (the one shown above is for my macOS machine) but can be shown with the `--help` switch. That location can be overriden with the `--config` option.
- If there is no config file, the key and secret can be passed as options on the command line or as environment variables (`FLICKR_API_KEY` and `FLICKR_API_SECRET`).

#### Log in to Flickr and authorize the application

The first time the tool is run on the command-line, a token for accessing the API must be generated. It is pretty straightforward:
- A web page in the default browser will open. 
- If not logged in to Flickr, a Flickr login screen will be presented in order to log in to Flickr. 
- Then a request to grant permission to the application is made: The permission is only given for the specific API key obtained when registering yourself.
- Once permission has been granted by the logged in user, a 9-digit code will be displayed: It needs to be copied and pasted on the command line after the prompt "Verifier code:".

After that process, an access token will be cached inside an `oauth-tokens.sqlite` file stored on the same directory as the default location of the API key config file (which can vary depending on the OS ; See above).

As long as the token is cached, there will be no need no login again for subsequent runs (that is until the token expires).

The tool will run with the permission of the user that logged in. In order to switch user, the `oauth-tokens.sqlite` will need to be deleted.

# Examples

### Basic usage

The following command will synch the location data found in the GPX file with a single image, moving forward the time in the image by 2 minutes and 25 seconds:

```console
gpx2exif image geopaparazzi_20200315_183754.gpx dsc004239.jpg --delta 2m25s
```

After running this command, the photo will be updated with the location of the GPX track point that is the closest in time.

### Folder

Instead of a single file, it is possible to pass a folder:

```console
gpx2exif image geopaparazzi_20200315_183754.gpx photos --delta 2m25s
```

### Flickr

You must get the URL of an album from Flickr. 

```console
gpx2exif flickr geopaparazzi_20200315_183754.gpx https://www.flickr.com/photos/o_0/albums/72157713927736642 --delta 2m25s
```

(the API key and secret come from a config file and do not need to be passed to the command)
