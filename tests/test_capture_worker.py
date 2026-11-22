import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from imgtrim_ui.capture_worker import SequenceCaptureWorker
from imgtrim_ui.trim_app import TrimApp
from imgtrim_ui.target_window import TargetWindowManager
import imgtrim_ui.sequence_app as sequence_app
from imgtrim_gui import get_trim_app_class
from seq_capture import CaptureApp


class FakeMSS:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class CaptureWorkerTests(unittest.TestCase):
    def test_legacy_launchers_share_the_package_implementations(self):
        self.assertIs(get_trim_app_class(), TrimApp)
        self.assertEqual(CaptureApp.__module__, "imgtrim_ui.sequence_app")

    def test_capture_app_keeps_trim_and_output_dialog_integrations(self):
        app = object.__new__(CaptureApp)
        app.root = object()
        app.output_dir = SimpleNamespace(get=lambda: "out")

        with patch("imgtrim_ui.sequence_app.open_trim_window") as open_trim:
            app.open_trim_tool()

        open_trim.assert_called_once_with(
            app.root, input_dir="out", output_dir=str(Path("out") / "trimmed")
        )

        with patch(
            "imgtrim_ui.sequence_app.filedialog.askdirectory",
            return_value="",
        ) as ask_directory:
            app.choose_output()

        ask_directory.assert_called_once_with(
            title="保存先を選択", initialdir=str(sequence_app.APP_DIR)
        )

    def test_target_window_manager_uses_app_owned_handle(self):
        app = SimpleNamespace(target_hwnd=123)
        manager = TargetWindowManager(app)

        with patch(
            "imgtrim_ui.target_window.get_window_rect",
            return_value=(10, 20, 300, 200),
        ) as get_rect:
            self.assertEqual(manager.get_target_rect(), (10, 20, 300, 200))
            manager.get_target_rect(456)

        self.assertEqual(
            [entry.args[0] for entry in get_rect.call_args_list],
            [123, 456],
        )

    def make_app(self, *, page=3, end_page=3):
        scheduled = []
        app = SimpleNamespace()
        app.stop_event = threading.Event()
        app.pause_event = threading.Event()
        app.pause_generation = 0
        app.state_lock = threading.Lock()
        app.target_hwnd = 0
        app.capture_config = {
            "current_page": page,
            "end_page": end_page,
            "x": 20,
            "y": 30,
            "w": 40,
            "h": 50,
            "capture_delay": 0,
            "page_delay": 0,
            "prefix": "page_",
            "out": "output",
            "page_key": "Right",
            "start_page": 1,
        }
        app.resolve_region_values = lambda *args, **kwargs: (20, 30, 40, 50)
        app.update_after_capture = object()
        app.set_current_page = object()
        app.finish_capture = object()
        app.finish_with_error = lambda _message: None
        app.root = SimpleNamespace(
            after=lambda delay, callback, *args: scheduled.append(
                (delay, callback, args)
            )
        )
        return app, scheduled

    def test_run_saves_resolved_region_and_schedules_ui_updates(self):
        app, scheduled = self.make_app()
        output_path = Path("output/page_0003.png")

        with (
            patch("imgtrim_ui.capture_worker.mss.MSS", return_value=FakeMSS()),
            patch(
                "imgtrim_ui.capture_worker.build_sequence_output_path",
                return_value=output_path,
            ) as build_path,
            patch(
                "imgtrim_ui.capture_worker.save_resolved_region_png"
            ) as save_png,
        ):
            SequenceCaptureWorker(app).run()

        build_path.assert_called_once_with(
            "output",
            prefix="page_",
            page=3,
            start_page=1,
            filename_start=1,
            filename_digits=4,
            overwrite=True,
            suffix="_copy",
        )
        save_png.assert_called_once_with(
            output_path,
            (20, 30, 40, 50),
            sct=unittest.mock.ANY,
            compress_level=1,
        )
        self.assertEqual(
            scheduled,
            [
                (0, app.update_after_capture, (3, 3)),
                (0, app.finish_capture, ()),
            ],
        )

    def test_run_advances_pages_and_saves_each_sequence_frame(self):
        app, scheduled = self.make_app(page=1, end_page=2)

        with (
            patch("imgtrim_ui.capture_worker.mss.MSS", return_value=FakeMSS()),
            patch(
                "imgtrim_ui.capture_worker.build_sequence_output_path",
                side_effect=[Path("output/page_0001.png"), Path("output/page_0002.png")],
            ),
            patch(
                "imgtrim_ui.capture_worker.save_resolved_region_png"
            ) as save_png,
            patch("imgtrim_ui.capture_worker.send_page_key") as send_key,
        ):
            SequenceCaptureWorker(app).run()

        self.assertEqual(save_png.call_count, 2)
        self.assertEqual(
            [call.args[1] for call in save_png.call_args_list],
            [(20, 30, 40, 50), (20, 30, 40, 50)],
        )
        send_key.assert_called_once_with("Right")
        self.assertEqual(app.capture_config["current_page"], 2)
        self.assertEqual(
            [callback for _delay, callback, _args in scheduled],
            [
                app.update_after_capture,
                app.set_current_page,
                app.update_after_capture,
                app.finish_capture,
            ],
        )


if __name__ == "__main__":
    unittest.main()
