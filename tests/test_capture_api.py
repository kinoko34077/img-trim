import tempfile
import unittest
from pathlib import Path

from PIL import Image

from imgtrim_core.capture_api import save_resolved_region_png
from seq_capture import CaptureApp


class FakeShot:
    def __init__(self, width, height):
        self.size = (width, height)
        self.bgra = bytes(width * height * 4)


class FakeMSS:
    def __init__(self, size_adjustment=(0, 0)):
        self.requested_region = None
        self.size_adjustment = size_adjustment

    def grab(self, region):
        self.requested_region = dict(region)
        return FakeShot(
            region["width"] + self.size_adjustment[0],
            region["height"] + self.size_adjustment[1],
        )


class SaveResolvedRegionTests(unittest.TestCase):
    def test_png_uses_resolved_region_dimensions(self):
        # Center-absolute input combines opposing margins into the final size.
        app = object.__new__(CaptureApp)
        app.get_target_rect = lambda _hwnd=None: (100, 200, 800, 600)
        region = CaptureApp.resolve_region_values(
            app,
            400,
            300,
            400,
            300,
            input_mode="center_abs",
            relative_to_window=True,
            hwnd=1,
        )
        self.assertEqual(region, (100, 200, 800, 600))
        fake_sct = FakeMSS()

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "page_0001.png"
            save_resolved_region_png(output, region, sct=fake_sct)

            with Image.open(output) as image:
                self.assertEqual(image.size, (800, 600))

        self.assertEqual(
            fake_sct.requested_region,
            {"left": 100, "top": 200, "width": 800, "height": 600},
        )

    def test_png_rejects_mss_result_with_wrong_dimensions(self):
        fake_sct = FakeMSS(size_adjustment=(-1, 0))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "page_0001.png"
            with self.assertRaisesRegex(
                RuntimeError,
                "returned 799x600; requested 800x600",
            ):
                save_resolved_region_png(
                    output,
                    (100, 200, 800, 600),
                    sct=fake_sct,
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
