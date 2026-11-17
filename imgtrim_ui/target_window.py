"""Windows foreground-target discovery, focus, and geometry operations."""

import ctypes
from ctypes import wintypes
import os
import time

from imgtrim_core.app_runtime import SW_RESTORE, user32
from imgtrim_core.capture_api import get_window_rect


class TargetWindowManager:
    """Manage target-window operations using state owned by the app controller."""

    def __init__(self, app):
        self.app = app

    def get_target_rect(
        self,
        hwnd=None
    ):
        if hwnd is None:
            hwnd = self.app.target_hwnd

        return get_window_rect(
            hwnd
        )


    def capture_foreground_target(self):

        if not self.app.running:

            hwnd = (
                user32.GetForegroundWindow()
            )

            if hwnd:

                pid = (
                    wintypes.DWORD()
                )

                user32.GetWindowThreadProcessId(
                    hwnd,
                    ctypes.byref(pid)
                )

                # 自分自身のGUIは対象にしない
                if (
                    pid.value
                    != os.getpid()
                ):

                    self.app.target_hwnd = hwnd

                    length = (
                        user32
                        .GetWindowTextLengthW(
                            hwnd
                        )
                    )

                    buffer = (
                        ctypes
                        .create_unicode_buffer(
                            length + 1
                        )
                    )

                    user32.GetWindowTextW(
                        hwnd,
                        buffer,
                        length + 1
                    )

                    title = (
                        buffer.value
                        or "(無題)"
                    )

                    if len(title) > 55:
                        title = (
                            title[:55]
                            + "…"
                        )

                    self.app.target_name.set(
                        "対象ウィンドウ："
                        + title
                    )

        return (
            self.get_target_rect()
            is not None
        )


    def acquire_target_window(
        self,
        refresh=False
    ):
        if (
            not refresh
            and self.get_target_rect()
            is not None
        ):
            return True

        try:
            previous_state = self.app.root.state()
        except Exception:
            previous_state = "normal"

        try:
            self.app.root.withdraw()
            self.app.root.update()

            time.sleep(
                0.18
            )

            self.capture_foreground_target()

        finally:
            try:
                self.app.root.deiconify()

                if previous_state == "zoomed":
                    self.app.root.state(
                        "zoomed"
                    )

                self.app.root.lift()
                self.app.root.update_idletasks()
            except Exception:
                pass

        return (
            self.get_target_rect()
            is not None
        )


    def activate_target(
        self,
        hwnd=None
    ):

        if hwnd is None:
            hwnd = self.app.target_hwnd

        if (
            not hwnd
            or not user32.IsWindow(
                hwnd
            )
        ):
            return False

        try:
            user32.ShowWindow(
                hwnd,
                SW_RESTORE
            )

            foreground = user32.GetForegroundWindow()
            current_thread = (
                ctypes.windll.kernel32.GetCurrentThreadId()
            )
            target_thread = (
                user32.GetWindowThreadProcessId(
                    hwnd,
                    None
                )
            )
            foreground_thread = 0

            if foreground:
                foreground_thread = (
                    user32.GetWindowThreadProcessId(
                        foreground,
                        None
                    )
                )

            attached_target = False
            attached_foreground = False

            try:
                if target_thread:
                    attached_target = bool(
                        user32.AttachThreadInput(
                            current_thread,
                            target_thread,
                            True
                        )
                    )

                if (
                    foreground_thread
                    and foreground_thread != target_thread
                ):
                    attached_foreground = bool(
                        user32.AttachThreadInput(
                            current_thread,
                            foreground_thread,
                            True
                        )
                    )

                user32.BringWindowToTop(
                    hwnd
                )
                user32.SetForegroundWindow(
                    hwnd
                )
                try:
                    user32.SwitchToThisWindow(
                        hwnd,
                        True
                    )
                except Exception:
                    pass

                user32.SetFocus(
                    hwnd
                )
                user32.SetActiveWindow(
                    hwnd
                )

            finally:
                if attached_foreground:
                    user32.AttachThreadInput(
                        current_thread,
                        foreground_thread,
                        False
                    )

                if attached_target:
                    user32.AttachThreadInput(
                        current_thread,
                        target_thread,
                        False
                    )

            for _index in range(10):
                foreground = user32.GetForegroundWindow()

                if (
                    foreground == hwnd
                    or bool(
                        user32.IsChild(
                            hwnd,
                            foreground
                        )
                    )
                ):
                    return True

                time.sleep(
                    0.03
                )

            return False

        except Exception:
            return False


    def is_target_active(
        self,
        hwnd=None
    ):
        if hwnd is None:
            hwnd = self.app.target_hwnd

        if (
            not hwnd
            or not user32.IsWindow(
                hwnd
            )
        ):
            return False

        foreground = user32.GetForegroundWindow()

        return (
            foreground == hwnd
            or bool(
                user32.IsChild(
                    hwnd,
                    foreground
                )
            )
        )
