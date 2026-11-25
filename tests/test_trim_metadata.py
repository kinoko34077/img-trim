import tempfile
import unittest
from pathlib import Path

from PIL import Image

from imgtrim_core.trim_api import TrimMargins, trim_image_to_path


def make_exif(orientation):
    exif = Image.Exif()
    exif[0x0112] = orientation
    return exif


class TrimMetadataTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.dir = Path(self._temp.name)

    def tearDown(self):
        self._temp.cleanup()

    def test_jpeg_keeps_exif_orientation_and_dpi(self):
        source = self.dir / "a.jpg"
        Image.new("RGB", (40, 20), (255, 0, 0)).save(
            source, exif=make_exif(6), dpi=(300, 300)
        )
        output = self.dir / "out.jpg"
        trim_image_to_path(source, output, TrimMargins(1, 1, 1, 1))
        with Image.open(output) as result:
            self.assertEqual(result.size, (38, 18))
            self.assertEqual(result.getexif().get(0x0112), 6)
            self.assertEqual(round(result.info["dpi"][0]), 300)

    def test_png_keeps_dpi_and_icc_profile(self):
        from PIL import ImageCms

        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        source = self.dir / "b.png"
        Image.new("RGB", (10, 10), (0, 255, 0)).save(
            source, dpi=(144, 144), icc_profile=icc
        )
        output = self.dir / "out.png"
        trim_image_to_path(source, output, TrimMargins(1, 1, 1, 1))
        with Image.open(output) as result:
            self.assertEqual(result.info.get("icc_profile"), icc)
            self.assertEqual(round(result.info["dpi"][0]), 144)

    def test_image_without_metadata_still_saves(self):
        source = self.dir / "c.bmp"
        Image.new("RGB", (8, 8), (0, 0, 255)).save(source)
        output = self.dir / "out.bmp"
        trim_image_to_path(source, output, TrimMargins(2, 2, 2, 2))
        with Image.open(output) as result:
            self.assertEqual(result.size, (4, 4))

    def test_rgba_to_jpeg_conversion_keeps_metadata(self):
        source = self.dir / "d.png"
        Image.new("RGBA", (12, 12), (1, 2, 3, 128)).save(source, dpi=(96, 96))
        output = self.dir / "out.jpg"
        trim_image_to_path(source, output, TrimMargins(1, 1, 1, 1))
        with Image.open(output) as result:
            self.assertEqual(result.mode, "RGB")
            self.assertEqual(round(result.info["dpi"][0]), 96)


if __name__ == "__main__":
    unittest.main()
