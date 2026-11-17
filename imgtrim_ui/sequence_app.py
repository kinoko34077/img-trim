from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
import ctypes
from ctypes import wintypes
import os
import threading
import time

import mss
from pynput import keyboard

from imgtrim_core.app_runtime import (
    SW_RESTORE,
    enable_dpi_awareness,
    user32,
)
from imgtrim_core.capture_api import (
    get_window_rect,
    resolve_region_absolute as resolve_capture_region_absolute,
)
from imgtrim_core.page_control import SPECIAL_KEYS as PAGE_SPECIAL_KEYS

from imgtrim_core.app_paths import application_dir
from imgtrim_ui.region_selectors import LiveRegionSelector
from imgtrim_ui.capture_worker import SequenceCaptureWorker
from imgtrim_ui.sequence_view import build_capture_ui
from imgtrim_gui import open_trim_window


APP_DIR = application_dir()
INI_PATH = APP_DIR / "seq_capture.ini"


enable_dpi_awareness()


class CaptureApp:

    def __init__(
        self,
        root
    ):

        self.root = root

        self.root.title(
            "連番スクリーンショット"
        )

        self.root.geometry(
            "760x760"
        )

        self.root.resizable(
            True,
            True
        )

        self.root.minsize(
            640,
            520
        )

        # ----------------------------------------------------
        # 状態
        # ----------------------------------------------------

        self.target_hwnd = 0

        self.running = False
        self.paused = False

        self.worker = None

        self.stop_event = (
            threading.Event()
        )

        self.pause_event = (
            threading.Event()
        )

        self.pause_generation = 0

        self.state_lock = (
            threading.Lock()
        )

        self.capture_config = {}
        self.region_selector = None


        # ----------------------------------------------------
        # GUI変数
        # ----------------------------------------------------

        self.output_dir = (
            tk.StringVar()
        )

        self.region_x = (
            tk.StringVar(
                value="0"
            )
        )

        self.region_y = (
            tk.StringVar(
                value="0"
            )
        )

        self.region_w = (
            tk.StringVar(
                value="800"
            )
        )

        self.region_h = (
            tk.StringVar(
                value="600"
            )
        )

        self.region_input_mode = (
            tk.StringVar(
                value="corners"
            )
        )

        self.region_label_vars = [
            tk.StringVar(value="X1"),
            tk.StringVar(value="Y1"),
            tk.StringVar(value="X2"),
            tk.StringVar(value="Y2"),
        ]

        self.relative_to_window = (
            tk.BooleanVar(
                value=False
            )
        )

        self.page_key = (
            tk.StringVar(
                value="Right"
            )
        )

        self.start_page = (
            tk.StringVar(
                value="1"
            )
        )

        self.end_page = (
            tk.StringVar(
                value="100"
            )
        )

        self.current_page = (
            tk.StringVar(
                value="1"
            )
        )

        self.capture_delay = (
            tk.StringVar(
                value="150"
            )
        )

        self.page_delay = (
            tk.StringVar(
                value="500"
            )
        )

        self.prefix = (
            tk.StringVar(
                value="page_"
            )
        )

        self.filename_digits = (
            tk.StringVar(
                value="4"
            )
        )

        self.filename_start = (
            tk.StringVar(
                value="1"
            )
        )

        self.overwrite_existing = (
            tk.BooleanVar(
                value=True
            )
        )

        self.filename_suffix = (
            tk.StringVar(
                value="_copy"
            )
        )

        self.status = (
            tk.StringVar(
                value="停止中"
            )
        )

        self.target_name = (
            tk.StringVar(
                value=
                "対象ウィンドウ：未検出"
            )
        )

        self.region_summary = (
            tk.StringVar(
                value=""
            )
        )

        self.load_settings()

        self.build_gui()
        self.bind_region_watchers()
        self.update_region_labels()
        self.update_region_summary()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

        # 対象ウィンドウ追跡
        self.update_region_summary()

        # Esc global listener
        self.esc_listener = (
            keyboard.Listener(
                on_release=
                    self.on_global_key_release
            )
        )

        self.esc_listener.daemon = True
        self.esc_listener.start()


    # ========================================================
    # GUI生成
    # ========================================================

    def build_gui(self):
        build_capture_ui(self)


    def open_trim_tool(self):
        input_dir = self.output_dir.get().strip()
        output_dir = ""

        if input_dir:
            output_dir = str(
                Path(input_dir)
                / "trimmed"
            )

        try:
            open_trim_window(
                self.root,
                input_dir=input_dir,
                output_dir=output_dir
            )
        except Exception as e:
            messagebox.showerror(
                "\u30c8\u30ea\u30df\u30f3\u30b0",
                str(e)
            )


    # ========================================================
    # Region helpers
    # ========================================================

    def bind_region_watchers(self):
        watched = (
            self.region_x,
            self.region_y,
            self.region_w,
            self.region_h,
            self.region_input_mode,
            self.relative_to_window,
        )

        for var in watched:
            var.trace_add(
                "write",
                self.on_region_value_changed
            )


    def on_region_value_changed(
        self,
        *_args
    ):
        self.update_region_labels()
        self.update_region_summary()


    def on_region_mode_changed(self):
        self.update_region_labels()
        self.update_region_summary()
        self.save_settings()


    def update_region_labels(self):
        mode = self.region_input_mode.get()

        if mode == "center_abs":
            labels = (
                "左",
                "上",
                "右",
                "下"
            )
        elif mode == "size":
            labels = (
                "X",
                "Y",
                "幅",
                "高さ"
            )
        else:
            labels = (
                "X1",
                "Y1",
                "X2",
                "Y2"
            )

        for var, label in zip(
            self.region_label_vars,
            labels
        ):
            if var.get() != label:
                var.set(
                    label
                )


    def build_region_value_vars(self):
        return {
            "x": self.region_x,
            "y": self.region_y,
            "w": self.region_w,
            "h": self.region_h,
        }


    def get_target_rect(
        self,
        hwnd=None
    ):
        if hwnd is None:
            hwnd = self.target_hwnd

        return get_window_rect(
            hwnd
        )


    def resolve_region_absolute(
        self,
        x,
        y,
        width,
        height,
        relative_to_window=None,
        hwnd=None
    ):
        if relative_to_window is None:
            relative_to_window = (
                self.relative_to_window.get()
            )

        return resolve_capture_region_absolute(
            x,
            y,
            width,
            height,
            relative_to_window=relative_to_window,
            hwnd=hwnd,
        )


    def get_virtual_screen_rect(self):
        with mss.MSS() as sct:
            monitor = sct.monitors[0]

        return (
            monitor["left"],
            monitor["top"],
            monitor["width"],
            monitor["height"],
        )


    def resolve_region_values(
        self,
        a,
        b,
        c,
        d,
        *,
        input_mode=None,
        relative_to_window=None,
        hwnd=None
    ):
        if input_mode is None:
            input_mode = self.region_input_mode.get()

        if relative_to_window is None:
            relative_to_window = self.relative_to_window.get()

        if input_mode == "center_abs":
            left_abs = abs(a)
            top_abs = abs(b)
            right_abs = abs(c)
            bottom_abs = abs(d)

            if relative_to_window:
                base_rect = self.get_target_rect(
                    hwnd
                )
            else:
                base_rect = self.get_virtual_screen_rect()

            if base_rect is None:
                return None

            base_left, base_top, base_width, base_height = base_rect
            center_x = base_left + (base_width / 2)
            center_y = base_top + (base_height / 2)

            left = int(
                round(center_x - left_abs)
            )
            top = int(
                round(center_y - top_abs)
            )
            right = int(
                round(center_x + right_abs)
            )
            bottom = int(
                round(center_y + bottom_abs)
            )

            return (
                left,
                top,
                right - left,
                bottom - top,
            )

        if input_mode == "size":
            return self.resolve_region_absolute(
                a,
                b,
                c,
                d,
                relative_to_window=relative_to_window,
                hwnd=hwnd,
            )

        left = min(
            a,
            c
        )
        top = min(
            b,
            d
        )
        right = max(
            a,
            c
        )
        bottom = max(
            b,
            d
        )

        return self.resolve_region_absolute(
            left,
            top,
            right - left,
            bottom - top,
            relative_to_window=relative_to_window,
            hwnd=hwnd,
        )


    def selected_screen_region_to_values(
        self,
        left,
        top,
        width,
        height
    ):
        mode = self.region_input_mode.get()

        if mode == "size":
            if self.relative_to_window.get():
                base_rect = self.get_target_rect()

                if base_rect is not None:
                    base_left, base_top, _bw, _bh = base_rect
                    left -= base_left
                    top -= base_top

            return (
                left,
                top,
                width,
                height,
            )

        if mode == "center_abs":
            if self.relative_to_window.get():
                base_rect = self.get_target_rect()
            else:
                base_rect = self.get_virtual_screen_rect()

            if base_rect is None:
                return (
                    left,
                    top,
                    left + width,
                    top + height,
                )

            base_left, base_top, base_width, base_height = base_rect
            center_x = base_left + (base_width / 2)
            center_y = base_top + (base_height / 2)
            right = left + width
            bottom = top + height

            return (
                int(round(abs(center_x - left))),
                int(round(abs(center_y - top))),
                int(round(abs(right - center_x))),
                int(round(abs(bottom - center_y))),
            )

        if self.relative_to_window.get():
            base_rect = self.get_target_rect()

            if base_rect is not None:
                base_left, base_top, _bw, _bh = base_rect
                left -= base_left
                top -= base_top

        return (
            left,
            top,
            left + width,
            top + height,
        )


    def update_region_summary(self):
        try:
            a = int(self.region_x.get())
            b = int(self.region_y.get())
            c = int(self.region_w.get())
            d = int(self.region_h.get())
        except ValueError:
            self.region_summary.set(
                "checking region values"
            )
            return

        mode = self.region_input_mode.get()

        absolute = self.resolve_region_values(
            a,
            b,
            c,
            d,
            input_mode=mode
        )

        if absolute is None:
            self.region_summary.set(
                "target window is not selected or is invalid"
            )
            return

        abs_x, abs_y, width, height = absolute

        if mode == "center_abs":
            input_text = (
                f"center0 L={abs(a)} T={abs(b)} "
                f"R={abs(c)} B={abs(d)}"
            )
        elif mode == "size":
            input_text = (
                f"size X={a} Y={b} W={c} H={d}"
            )
        else:
            input_text = (
                f"coords X1={a} Y1={b} X2={c} Y2={d}"
            )

        base_text = ""

        if self.relative_to_window.get():
            base_rect = self.get_target_rect()
            if base_rect is not None:
                base_left, base_top, _bw, _bh = base_rect
                base_text = f" / base {base_left}, {base_top}"

        self.region_summary.set(
            f"{input_text}\n"
            f"absolute X={abs_x} Y={abs_y} W={width} H={height}"
            f"{base_text}"
        )


    # ========================================================
    # INI
    # ========================================================

    def load_settings(self):

        if not INI_PATH.exists():
            return

        cfg = (
            configparser.ConfigParser()
        )

        try:

            cfg.read(
                INI_PATH,
                encoding="utf-8"
            )

            section = (
                cfg["Settings"]
            )

            self.output_dir.set(
                section.get(
                    "output_dir",
                    ""
                )
            )

            self.region_x.set(
                section.get(
                    "region_x",
                    "0"
                )
            )

            self.region_y.set(
                section.get(
                    "region_y",
                    "0"
                )
            )

            self.region_w.set(
                section.get(
                    "region_w",
                    "800"
                )
            )

            self.region_h.set(
                section.get(
                    "region_h",
                    "600"
                )
            )

            region_input_mode = section.get(
                "region_input_mode",
                ""
            )

            if region_input_mode:
                self.region_input_mode.set(
                    region_input_mode
                )
            else:
                try:
                    legacy_x = int(self.region_x.get())
                    legacy_y = int(self.region_y.get())
                    legacy_w = int(self.region_w.get())
                    legacy_h = int(self.region_h.get())
                    self.region_w.set(
                        str(legacy_x + legacy_w)
                    )
                    self.region_h.set(
                        str(legacy_y + legacy_h)
                    )
                except ValueError:
                    pass

                self.region_input_mode.set(
                    "corners"
                )

            self.relative_to_window.set(
                section.getboolean(
                    "relative_to_window",
                    fallback=False
                )
            )

            self.page_key.set(
                section.get(
                    "page_key",
                    "Right"
                )
            )

            self.start_page.set(
                section.get(
                    "start_page",
                    "1"
                )
            )

            self.end_page.set(
                section.get(
                    "end_page",
                    "100"
                )
            )

            self.current_page.set(
                section.get(
                    "current_page",
                    "1"
                )
            )

            self.capture_delay.set(
                section.get(
                    "capture_delay",
                    "150"
                )
            )

            self.page_delay.set(
                section.get(
                    "page_delay",
                    "500"
                )
            )

            self.prefix.set(
                section.get(
                    "prefix",
                    "page_"
                )
            )

            self.filename_digits.set(
                section.get(
                    "filename_digits",
                    "4"
                )
            )

            self.filename_start.set(
                section.get(
                    "filename_start",
                    self.start_page.get()
                )
            )

            self.overwrite_existing.set(
                section.getboolean(
                    "overwrite_existing",
                    fallback=True
                )
            )

            self.filename_suffix.set(
                section.get(
                    "filename_suffix",
                    "_copy"
                )
            )

            window_geometry = section.get(
                "window_geometry",
                ""
            )

            if window_geometry:
                self.root.geometry(
                    window_geometry
                )

        except Exception as e:
            print(
                "INI読込エラー:",
                e
            )


    def save_settings(self):

        cfg = (
            configparser.ConfigParser()
        )

        cfg["Settings"] = {

            "output_dir":
                self.output_dir.get(),

            "region_x":
                self.region_x.get(),

            "region_y":
                self.region_y.get(),

            "region_w":
                self.region_w.get(),

            "region_h":
                self.region_h.get(),

            "region_input_mode":
                self.region_input_mode.get(),

            "relative_to_window":
                str(
                    self.relative_to_window.get()
                ),

            "page_key":
                self.page_key.get(),

            "start_page":
                self.start_page.get(),

            "end_page":
                self.end_page.get(),

            "current_page":
                self.current_page.get(),

            "capture_delay":
                self.capture_delay.get(),

            "page_delay":
                self.page_delay.get(),

            "prefix":
                self.prefix.get(),

            "filename_digits":
                self.filename_digits.get(),

            "filename_start":
                self.filename_start.get(),

            "overwrite_existing":
                str(
                    self.overwrite_existing.get()
                ),

            "filename_suffix":
                self.filename_suffix.get(),

            "window_geometry":
                self.root.geometry()
        }

        try:

            with open(
                INI_PATH,
                "w",
                encoding="utf-8"
            ) as file:

                cfg.write(
                    file
                )

        except Exception as e:

            print(
                "INI保存エラー:",
                e
            )


    # ========================================================
    # 対象window追跡
    # ========================================================

    def capture_foreground_target(self):

        if not self.running:

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

                    self.target_hwnd = hwnd

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

                    self.target_name.set(
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
            previous_state = self.root.state()
        except Exception:
            previous_state = "normal"

        try:
            self.root.withdraw()
            self.root.update()

            time.sleep(
                0.18
            )

            self.capture_foreground_target()

        finally:
            try:
                self.root.deiconify()

                if previous_state == "zoomed":
                    self.root.state(
                        "zoomed"
                    )

                self.root.lift()
                self.root.update_idletasks()
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
            hwnd = self.target_hwnd

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
            hwnd = self.target_hwnd

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


    # ========================================================
    # 保存先
    # ========================================================

    def choose_output(self):

        initial = (
            self.output_dir.get()
        )

        if not Path(
            initial
        ).is_dir():

            initial = str(
                APP_DIR
            )

        folder = (
            filedialog.askdirectory(
                title=
                    "保存先を選択",

                initialdir=
                    initial
            )
        )

        if folder:

            self.output_dir.set(
                folder
            )

            self.save_settings()


    # ========================================================
    # ページ送りキー入力
    # ========================================================

    def capture_page_key(self):

        dialog = tk.Toplevel(
            self.root
        )

        dialog.title(
            "ページ送りキー設定"
        )

        dialog.geometry(
            "340x120"
        )

        dialog.resizable(
            False,
            False
        )

        dialog.transient(
            self.root
        )

        dialog.grab_set()

        ttk.Label(
            dialog,
            text=
                "ページ送りに使うキーを押してください"
        ).pack(
            pady=(20, 8)
        )

        ttk.Label(
            dialog,
            text=
                "例：→ / PageDown / Space"
        ).pack()


        def on_key(event):

            key_name = (
                event.keysym
            )

            if key_name == "Escape":

                dialog.destroy()

                return "break"

            if (
                key_name
                not in PAGE_SPECIAL_KEYS
                and len(
                    event.char or ""
                ) == 1
            ):
                key_name = (
                    event.char
                )

            if (
                key_name
                not in PAGE_SPECIAL_KEYS
                and len(key_name) != 1
            ):

                messagebox.showerror(
                    "未対応",
                    (
                        "このキーは"
                        "未対応です: "
                        + key_name
                    ),
                    parent=dialog
                )

                return "break"

            self.page_key.set(
                key_name
            )

            self.save_settings()

            dialog.destroy()

            return "break"


        dialog.bind(
            "<KeyPress>",
            on_key
        )

        dialog.focus_force()


    # ========================================================
    # 領域指定
    # ========================================================

    def prepare_region_select(self):

        if self.running:
            return

        if self.relative_to_window.get():
            if not self.acquire_target_window(
                refresh=True
            ):
                messagebox.showerror(
                    "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u672a\u9078\u629e",
                    "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u3092\u524d\u9762\u306b\u3057\u3066\u304b\u3089\u3082\u3046\u4e00\u5ea6\u5b9f\u884c\u3057\u3066\u304f\u3060\u3055\u3044"
                )
                return

            if not self.is_target_active():
                self.activate_target()

            self.root.after(
                250,
                self.open_region_selector
            )

        else:

            self.open_region_selector()


    def open_region_selector(self):

        try:
            if self.region_selector is not None:
                self.region_selector.lift()
                return

            base_rect = None

            if self.relative_to_window.get():
                base_rect = self.get_target_rect()

                if base_rect is None:
                    messagebox.showerror(
                        "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u672a\u9078\u629e",
                        (
                            "\u76f8\u5bfe\u5ea7\u6a19\u3092\u4f7f\u3046\u306b\u306f "
                            "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u3092"
                            "\u30a2\u30af\u30c6\u30a3\u30d6\u306b\u3057\u3066\u304f\u3060\u3055\u3044"
                        )
                    )
                    return

            self.region_selector = LiveRegionSelector(
                self.root,
                self.apply_region,
                self.build_region_value_vars(),
                self.region_input_mode,
                base_rect=base_rect,
                target_label=self.target_name.get(),
                close_callback=
                    self.clear_region_selector
            )

        except Exception as e:

            messagebox.showerror(
                "領域選択エラー",
                str(e)
            )


    def clear_region_selector(self):
        self.region_selector = None


    def apply_region(
        self,
        x,
        y,
        width,
        height
    ):
        self.region_x.set(
            str(x)
        )

        self.region_y.set(
            str(y)
        )

        self.region_w.set(
            str(width)
        )

        self.region_h.set(
            str(height)
        )

        self.save_settings()
        self.update_region_summary()

        self.root.lift()


    # ========================================================
    # START
    # ========================================================

    def start_capture(self):

        if self.running:
            return

        try:

            output = Path(
                self.output_dir.get()
            )

            x = int(
                self.region_x.get()
            )

            y = int(
                self.region_y.get()
            )

            width = int(
                self.region_w.get()
            )

            height = int(
                self.region_h.get()
            )

            start = int(
                self.start_page.get()
            )

            end = int(
                self.end_page.get()
            )

            capture_delay = int(
                self.capture_delay.get()
            )

            page_delay = int(
                self.page_delay.get()
            )

            filename_digits = int(
                self.filename_digits.get()
            )

            filename_start = int(
                self.filename_start.get()
            )

            relative_to_window = (
                self.relative_to_window.get()
            )

            region_input_mode = (
                self.region_input_mode.get()
            )

        except ValueError:

            messagebox.showerror(
                "入力エラー",
                "数値欄を確認してください。"
            )

            return


        if not self.output_dir.get().strip():

            messagebox.showerror(
                "入力エラー",
                "保存先を指定してください。"
            )

            return




        if (
            start < 1
            or end < start
        ):

            messagebox.showerror(
                "入力エラー",
                "開始・終了ページが不正です。"
            )

            return


        if (
            capture_delay < 0
            or page_delay < 0
        ):

            messagebox.showerror(
                "入力エラー",
                "待機時間は0以上です。"
            )

            return


        if (
            filename_digits < 1
            or filename_start < 0
        ):

            messagebox.showerror(
                "入力エラー",
                "連番桁数は1以上、保存連番開始は0以上で指定してください。"
            )

            return


        if not self.acquire_target_window(refresh=True):

            messagebox.showerror(
                "対象未検出",
                (
                    "撮影対象のウィンドウを"
                    "一度クリックしてください。"
                )
            )

            return

        preview_region = self.resolve_region_values(
            x,
            y,
            width,
            height,
            input_mode=region_input_mode,
            relative_to_window=relative_to_window,
            hwnd=self.target_hwnd
        )

        if preview_region is None:
            messagebox.showerror(
                "input error",
                "could not resolve capture region; check target window"
            )
            return

        _preview_x, _preview_y, preview_w, preview_h = preview_region

        if (
            preview_w <= 0
            or preview_h <= 0
        ):
            messagebox.showerror(
                "input error",
                "capture region must be at least 1px wide and high"
            )
            return



        output.mkdir(
            parents=True,
            exist_ok=True
        )


        self.current_page.set(
            str(start)
        )

        self.progress["maximum"] = (
            end
            - start
            + 1
        )

        self.progress["value"] = 0


        # ----------------------------------------------------
        # Worker用設定
        # tkinter variableをworkerから直接触らない
        # ----------------------------------------------------

        with self.state_lock:

            self.capture_config = {

                "out":
                    output,

                "x":
                    x,

                "y":
                    y,

                "w":
                    width,

                "h":
                    height,

                "relative_to_window":
                    relative_to_window,

                "region_input_mode":
                    region_input_mode,

                "target_hwnd":
                    self.target_hwnd,

                "start_page":
                    start,

                "end_page":
                    end,

                "current_page":
                    start,

                "capture_delay":
                    capture_delay,

                "page_delay":
                    page_delay,

                "prefix":
                    self.prefix.get(),

                "filename_digits":
                    filename_digits,

                "filename_start":
                    filename_start,

                "overwrite_existing":
                    self.overwrite_existing.get(),

                "filename_suffix":
                    self.filename_suffix.get(),

                "page_key":
                    self.page_key.get()
            }


        self.running = True
        self.paused = False

        self.stop_event.clear()
        self.pause_event.clear()

        self.pause_generation += 1

        self.status.set(
            f"開始準備：{start} / {end}"
        )

        self.pause_button.configure(
            text="一時停止"
        )

        self.save_settings()

        if not self.activate_target():
            self.running = False
            self.status.set(
                "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u306e\u524d\u9762\u5316\u306b\u5931\u6557"
            )
            messagebox.showerror(
                "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6",
                "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u3092\u524d\u9762\u306b\u3067\u304d\u307e\u305b\u3093\u3067\u3057\u305f"
            )
            return

        self.root.after(
            300,
            self.start_capture_worker
        )


    def start_capture_worker(self):
        if not self.running:
            return

        self.worker = threading.Thread(
            target=
                self.capture_worker,
            daemon=True
        )

        self.worker.start()


    # ========================================================
    # STOP
    # ========================================================

    def stop_capture(self):

        if not self.running:
            return

        self.stop_event.set()

        self.pause_event.clear()

        self.paused = False

        self.status.set(
            "停止中…"
        )


    # ========================================================
    # PAUSE
    # ========================================================

    def toggle_pause(self):

        if not self.running:
            return


        # ----------------------------------------------------
        # 一時停止
        # ----------------------------------------------------

        if not self.paused:

            self.paused = True

            self.pause_event.set()

            self.pause_generation += 1

            self.status.set(
                "一時停止："
                + self.current_page.get()
            )

            self.pause_button.configure(
                text="再開"
            )

            self.root.lift()
            self.root.focus_force()


        # ----------------------------------------------------
        # 再開
        # ----------------------------------------------------

        else:

            try:

                page = int(
                    self.current_page.get()
                )

                relative_to_window = (
                    self.relative_to_window.get()
                )

                if (
                    relative_to_window
                    and self.get_target_rect() is None
                ):
                    messagebox.showerror(
                        "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u672a\u9078\u629e",
                        (
                            "\u76f8\u5bfe\u5ea7\u6a19\u3067\u518d\u958b\u3059\u308b\u306b\u306f "
                            "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u3092"
                            "\u30a2\u30af\u30c6\u30a3\u30d6\u306b\u3057\u3066\u304f\u3060\u3055\u3044"
                        )
                    )
                    return

                cfg_update = {

                    "current_page":
                        page,

                    "end_page":
                        int(
                            self.end_page.get()
                        ),

                    "x":
                        int(
                            self.region_x.get()
                        ),

                    "y":
                        int(
                            self.region_y.get()
                        ),

                    "w":
                        int(
                            self.region_w.get()
                        ),

                    "h":
                        int(
                            self.region_h.get()
                        ),

                    "relative_to_window":
                        relative_to_window,

                    "region_input_mode":
                        self.region_input_mode.get(),

                    "target_hwnd":
                        self.target_hwnd,

                    "capture_delay":
                        int(
                            self.capture_delay.get()
                        ),

                    "page_delay":
                        int(
                            self.page_delay.get()
                        ),

                    "prefix":
                        self.prefix.get(),

                    "filename_digits":
                        int(
                            self.filename_digits.get()
                        ),

                    "filename_start":
                        int(
                            self.filename_start.get()
                        ),

                    "overwrite_existing":
                        self.overwrite_existing.get(),

                    "filename_suffix":
                        self.filename_suffix.get(),

                    "page_key":
                        self.page_key.get(),

                    "out":
                        Path(
                            self.output_dir.get()
                        )
                }

            except ValueError:

                messagebox.showerror(
                    "入力エラー",
                    "設定値を確認してください。"
                )

                return


            with self.state_lock:
                self.capture_config.update(
                    cfg_update
                )


            self.paused = False

            self.pause_generation += 1

            self.pause_event.clear()

            self.pause_button.configure(
                text="一時停止"
            )

            self.status.set(
                f"再開：{page}"
            )

            self.save_settings()

            if not self.is_target_active():
                self.activate_target()


    # ========================================================
    # ESC global
    # ========================================================

    def on_global_key_release(
        self,
        key
    ):

        if (
            key
            == keyboard.Key.esc
            and self.running
        ):

            self.root.after(
                0,
                self.toggle_pause
            )


    # ========================================================
    # 待機
    # ========================================================

    def wait_interruptible(self, seconds, generation):
        return SequenceCaptureWorker(self).wait_interruptible(seconds, generation)


    def wait_until_resumed(self):
        return SequenceCaptureWorker(self).wait_until_resumed()


    # ========================================================
    # 撮影Worker
    # ========================================================

    def capture_worker(self):
        SequenceCaptureWorker(self).run()


    # ========================================================
    # GUI更新
    # ========================================================

    def update_after_capture(
        self,
        page,
        end_page
    ):

        start = int(
            self.start_page.get()
        )

        self.progress["value"] = max(
            0,
            page
            - start
            + 1
        )

        self.status.set(
            f"撮影完了：{page} / {end_page}"
        )


    def set_current_page(
        self,
        page
    ):

        self.current_page.set(
            str(page)
        )

        self.status.set(
            f"ページ読込待機：{page}"
        )


    # ========================================================
    # 完了
    # ========================================================

    def finish_capture(self):

        was_stopped = (
            self.stop_event.is_set()
        )

        self.running = False
        self.paused = False

        self.stop_event.clear()
        self.pause_event.clear()

        self.pause_button.configure(
            text="一時停止"
        )

        if was_stopped:

            self.status.set(
                "停止"
            )

        else:

            self.status.set(
                "完了："
                + self.current_page.get()
            )

        self.save_settings()


    # ========================================================
    # エラー
    # ========================================================

    def finish_with_error(
        self,
        text
    ):

        self.running = False
        self.paused = False

        self.stop_event.set()
        self.pause_event.clear()

        self.pause_button.configure(
            text="一時停止"
        )

        self.status.set(
            "エラー停止"
        )

        messagebox.showerror(
            "エラー",
            text
        )


    # ========================================================
    # 終了
    # ========================================================

    def on_close(self):

        self.save_settings()

        self.stop_event.set()

        try:
            self.esc_listener.stop()

        except Exception:
            pass

        self.root.destroy()



def main() -> None:
    root = tk.Tk()
    CaptureApp(root)
    root.mainloop()
