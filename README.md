# gpx2exif

Simple command-line tool to add GPS info from a GPX file to EXIF tags in local images or to images hosted on Flickr

# Motivation

I use [GPS Logger](http://www.basicairdata.eu/projects/android/android-gps-logger/) on my Android phone to log GPS positions during a walk or hike. The app can export into GPX format, which gives the itinerary, as well as the times for my positions at a relatively high temporal resolution. This is useful for making maps or writing a guide after the fact. I also wanted to make it easier to know the location of the photos taken during the walk and have them show up on the Flickr map. Since my camera doesn't have any GPS logging equipment, I made this tool in order to add the GPS information to the photo EXIF tags based on the GPX tracking points.

I also had some GPX recordings corresponding to Flickr images that I had uploaded before I made this tool, so I have also added a way to set the location of existing Flickr images based on a GPX file.

# Install

The tool requires Python 3.7+ (since gpx2exif version 10; previous versions run on Python 3.6 as well).

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

Instead of a fixed offset with `--delta-tz`, it is possible to use a named timezone (for example "Europe/Paris") with the `--tz` option. In that case, the offset will be computed based on the date at the beginning of the GPX. If the GPX track spans a change in DST (ie multiple offsets), a warning will be issued. A special value "auto" can be used to take the current timezone of the computer.

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

The `--delta` switch can be present multiple times if needed.

The time shift can also be negative. For example:

```
-23m
```

### Time difference

It is also possible to indicate the time shift as a difference between the reference time (of the phone or GPS recorder) and the time of the camera:

```
16:42:05-16:48:59
```

### Read the time shift from a photo

The time difference can be useful when taking a picture of the clock on the phone / GPS recorder. Then the reference time can be read from the photo, while the camera time can be obtained from the EXIF of the photo file. On top of that, the `-z` option should be set to indicate the timezone (since the reference would be in local time). If the camera drifts a lot (it is the case on one of my cameras), this process can be done after every photo session to keep the time shift accurate.

To automate this workflow further, the `extract-time` subcommand can be used: It uses [GCP Cloud Vision](https://cloud.google.com/vision/docs/ocr) to read the time from a photo of the phone clock and outputs a time shift in the format expected by `gpx2exif` ie `3m54s`: It actually computes the time shift, instead of keeping the shift as a time difference like in the section above. If you use it, you need to setup a GCP project and enable the Cloud Vision API on your side. You will also possibly need to setup credentials and the GCP project name (see the [extract-time subcommand](#extract-time-subcommand) section). It may also not work depending on the phone clock: I use a Samsung phone and the format of the clock must be something like `7:12:23`.

# Commands

To get some help about the arguments to the command, just launch with the --help option.

`gpx2exif --help`

The `--help` option can also be used for the subcommands.

## `image` subcommand

The image subcommand allows to synch a GPX file with an image file or a folder of image files on a local disk.

`gpx2exif image ...`

## `flickr` subcommand

The flickr subcommand allows to synch a GPX file with images hosted on Flickr. 

`gpx2exif flickr ...`

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

## `extract-time` subcommand

The `extract-time` subcommand allows you to extract the time from a photo of a clock and compute the time difference with the EXIF time of the photo. This is useful to calculate the `--delta` to apply to a batch of photos.

`gpx2exif extract-time ...`

### Optional dependency

To install the dependency for this command, add the `vision` extra when installing `gpx2exif`. For example with `pip`:

`pip install gpx2exif[vision]`

### Authentication 

Authentication with Google Cloud (as well as the selection of a project) is handled by the client library: 

- If a service account is used, the `GOOGLE_APPLICATION_CREDENTIALS` environment variable can be set to the location of a credential JSON file. The GCP project used will be the one to which the SA belongs.
- If using **Application Default Credentials** (with `gcloud auth application-default login`), the project can be set with the `GOOGLE_CLOUD_PROJECT` env var.

See the [Google Cloud SDK documentation](https://cloud.google.com/docs/authentication/application-default-credentials) for more details.

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

# TODO

- pyinstaller.exe .\pyinstaller_bootstrap\main.py -p . --noconfirm -F -n gpx2exif
- way to easily reverse time change written to image (output command that will work)