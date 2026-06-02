from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from gpx2exif.gpx2flickr import (
    format_flickr_date_taken,
    gpx2flickr,
    process_image,
)


def make_flickr():
    return SimpleNamespace(
        photos=SimpleNamespace(
            setDates=MagicMock(),
            geo=SimpleNamespace(
                setLocation=MagicMock(),
                removeLocation=MagicMock(),
            ),
        )
    )


def make_image():
    return SimpleNamespace(
        id="123",
        datetaken="2025-10-24 06:54:23",
        latitude=0,
    )


class FlickrDateTakenTest(unittest.TestCase):
    def test_format_flickr_date_taken_omits_timezone(self):
        dt = datetime(
            2025,
            10,
            24,
            6,
            54,
            23,
            tzinfo=timezone(timedelta(hours=2)),
        )

        self.assertEqual(format_flickr_date_taken(dt), "2025-10-24 06:54:23")

    def test_process_image_uses_tz_delta_for_lookup_not_date_update(self):
        flickr = make_flickr()
        image = make_image()
        user = SimpleNamespace(id="user-id")
        delta_time = timedelta(minutes=2, seconds=25)
        delta_tz = timedelta(hours=-2)
        delta_total = delta_time + delta_tz

        with patch("gpx2exif.gpx2flickr.compute_pos", return_value=(1.0, 2.0)) as pos:
            result = process_image(
                flickr,
                image,
                user,
                [],
                delta_total,
                delta_time,
                timedelta(seconds=10),
                is_clear=False,
                is_update_images=True,
                is_update_time=True,
            )

        original = datetime(2025, 10, 24, 6, 54, 23, tzinfo=timezone.utc)
        self.assertEqual(result, (1.0, 2.0))
        pos.assert_called_once_with(original + delta_total, [], timedelta(seconds=10))
        flickr.photos.setDates.assert_called_once_with(
            photo_id="123",
            date_taken="2025-10-24 06:56:48",
            date_taken_granularity=0,
        )
        flickr.photos.geo.setLocation.assert_called_once_with(
            photo_id="123", lat=1.0, lon=2.0
        )

    def test_process_image_updates_date_even_without_position(self):
        flickr = make_flickr()
        image = make_image()
        user = SimpleNamespace(id="user-id")

        with (
            patch("gpx2exif.gpx2flickr.compute_pos", return_value=None),
            patch("gpx2exif.gpx2flickr.logger.warning"),
        ):
            result = process_image(
                flickr,
                image,
                user,
                [],
                timedelta(hours=1),
                timedelta(minutes=5),
                timedelta(seconds=10),
                is_clear=False,
                is_update_images=True,
                is_update_time=True,
            )

        self.assertIsNone(result)
        flickr.photos.setDates.assert_called_once_with(
            photo_id="123",
            date_taken="2025-10-24 06:59:23",
            date_taken_granularity=0,
        )
        flickr.photos.geo.setLocation.assert_not_called()

    def test_process_image_does_not_update_date_when_updates_disabled(self):
        flickr = make_flickr()
        image = make_image()
        user = SimpleNamespace(id="user-id")

        with patch("gpx2exif.gpx2flickr.compute_pos", return_value=(1.0, 2.0)):
            result = process_image(
                flickr,
                image,
                user,
                [],
                timedelta(minutes=5),
                timedelta(minutes=5),
                timedelta(seconds=10),
                is_clear=False,
                is_update_images=False,
                is_update_time=True,
            )

        self.assertEqual(result, (1.0, 2.0))
        flickr.photos.setDates.assert_not_called()
        flickr.photos.geo.setLocation.assert_not_called()

    def test_flickr_help_shows_update_time(self):
        result = CliRunner().invoke(gpx2flickr, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("--update-time", result.output)


if __name__ == "__main__":
    unittest.main()
