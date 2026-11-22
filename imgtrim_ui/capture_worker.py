"""Background sequence capture loop and interruptible timing."""

import time
import mss

from imgtrim_core.capture_api import (
    build_sequence_output_path,
    save_resolved_region_png,
)
from imgtrim_core.page_control import send_key as send_page_key


class SequenceCaptureWorker:
    """Run one capture session using the controller's state and callbacks."""

    def __init__(self, app):
        self.app = app

    def wait_interruptible(
        self,
        milliseconds,
        generation
    ):

        end_time = (
            time.monotonic()
            + milliseconds / 1000
        )

        while (
            time.monotonic()
            < end_time
        ):

            if self.app.stop_event.is_set():
                return "stop"

            if (
                self.app.pause_event.is_set()
                or generation
                != self.app.pause_generation
            ):
                return "restart"

            time.sleep(
                0.01
            )

        return "ok"


    def wait_until_resumed(self):

        while self.app.pause_event.is_set():

            if self.app.stop_event.is_set():
                return False

            time.sleep(
                0.03
            )

        return (
            not self.app.stop_event.is_set()
        )


    def run(self):

        try:

            with mss.MSS() as sct:

                while (
                    not
                    self.app.stop_event.is_set()
                ):

                    if not self.wait_until_resumed():
                        break

                    with self.app.state_lock:
                        cfg = dict(
                            self.app.capture_config
                        )

                    page = (
                        cfg["current_page"]
                    )

                    end_page = (
                        cfg["end_page"]
                    )

                    x = cfg["x"]
                    y = cfg["y"]

                    width = cfg["w"]
                    height = cfg["h"]

                    relative_to_window = (
                        cfg.get(
                            "relative_to_window",
                            False
                        )
                    )

                    region_input_mode = cfg.get(
                        "region_input_mode",
                        "corners"
                    )

                    target_hwnd = cfg.get(
                        "target_hwnd",
                        self.app.target_hwnd
                    )

                    capture_delay = (
                        cfg[
                            "capture_delay"
                        ]
                    )

                    page_delay = (
                        cfg["page_delay"]
                    )

                    prefix = (
                        cfg["prefix"]
                    )

                    filename_digits = cfg.get(
                        "filename_digits",
                        4
                    )

                    filename_start = cfg.get(
                        "filename_start",
                        cfg.get(
                            "start_page",
                            1
                        )
                    )

                    overwrite_existing = cfg.get(
                        "overwrite_existing",
                        True
                    )

                    filename_suffix = cfg.get(
                        "filename_suffix",
                        "_copy"
                    )

                    output = (
                        cfg["out"]
                    )

                    page_key = (
                        cfg["page_key"]
                    )


                    if page > end_page:
                        break


                    generation = (
                        self.app.pause_generation
                    )


                    # =========================================
                    # screenshot
                    # =========================================

                    absolute_region = (
                        self.app.resolve_region_values(
                            x,
                            y,
                            width,
                            height,
                            input_mode=region_input_mode,
                            relative_to_window=
                                relative_to_window,
                            hwnd=target_hwnd
                        )
                    )

                    if absolute_region is None:
                        self.app.root.after(
                            0,
                            lambda:
                                self.app.finish_with_error(
                                    "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u304c\u898b\u3064\u304b\u3089\u305a\u30ad\u30e3\u30d7\u30c1\u30e3\u3092\u7d9a\u884c\u3067\u304d\u307e\u305b\u3093"
                                )
                        )
                        return

                    output_path = build_sequence_output_path(
                        output,
                        prefix=prefix,
                        page=page,
                        start_page=cfg.get(
                            "start_page",
                            page
                        ),
                        filename_start=filename_start,
                        filename_digits=filename_digits,
                        overwrite=overwrite_existing,
                        suffix=filename_suffix
                    )


                    # =========================================
                    # 低圧縮PNG
                    # =========================================

                    save_resolved_region_png(
                        output_path,
                        absolute_region,
                        sct=sct,
                        compress_level=1
                    )


                    self.app.root.after(
                        0,
                        self.app.update_after_capture,
                        page,
                        end_page
                    )


                    if page >= end_page:
                        break


                    # =========================================
                    # 撮影後待機
                    # =========================================

                    result = (
                        self.wait_interruptible(
                            capture_delay,
                            generation
                        )
                    )


                    if result == "stop":
                        break


                    if result == "restart":
                        continue


                    # =========================================
                    # ページ送り
                    # =========================================

                    try:

                        if (
                            target_hwnd
                            and not self.app.is_target_active(
                                target_hwnd
                            )
                        ):
                            self.app.activate_target(
                                target_hwnd
                            )
                            time.sleep(
                                0.05
                            )

                        send_page_key(
                            page_key
                        )

                    except Exception as e:

                        self.app.root.after(
                            0,
                            lambda e=e:
                                self.app.finish_with_error(
                                    str(e)
                                )
                        )

                        return


                    next_page = (
                        page + 1
                    )


                    with self.app.state_lock:

                        self.app.capture_config[
                            "current_page"
                        ] = next_page


                    self.app.root.after(
                        0,
                        self.app.set_current_page,
                        next_page
                    )


                    # =========================================
                    # ページ読込待機
                    # =========================================

                    result = (
                        self.wait_interruptible(
                            page_delay,
                            generation
                        )
                    )


                    if result == "stop":
                        break


                    if result == "restart":
                        continue


            self.app.root.after(
                0,
                self.app.finish_capture
            )


        except Exception as e:

            self.app.root.after(
                0,
                lambda e=e:
                    self.app.finish_with_error(
                        str(e)
                    )
            )
