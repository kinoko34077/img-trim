from pathlib import Path
from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
import ctypes
from ctypes import wintypes
import os
import sys
import threading
import time

import mss
from pynput import keyboard

from imgtrim_core.app_runtime import (
    SW_RESTORE,
    cursor_hint_rect,
    enable_dpi_awareness,
    move_toplevel_absolute,
    pick_screen_monitor,
    user32,
)
from imgtrim_core.capture_api import (
    build_sequence_output_path,
    get_window_rect,
    image_from_mss_shot,
    resolve_region_absolute as resolve_capture_region_absolute,
    save_region_png,
)
from imgtrim_core.page_control import (
    SPECIAL_KEYS as PAGE_SPECIAL_KEYS,
    send_key as send_page_key,
)
from imgtrim_gui import open_trim_window


# ============================================================
# 基本設定
# ============================================================

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

INI_PATH = APP_DIR / "seq_capture.ini"


enable_dpi_awareness()


# ============================================================
# 領域選択
# ============================================================

class RegionSelector:

    MAG_RADIUS = 14
    MAG_SCALE = 10

    def __init__(
        self,
        root,
        callback
    ):
        self.root = root
        self.callback = callback

        self.start_x = None
        self.start_y = None

        self.rect_id = None
        self.photo = None

        # ----------------------------------------------------
        # overlay表示前の画面を取得
        # 拡大鏡にはこの画像を使う
        # ----------------------------------------------------

        with mss.MSS() as sct:

            monitor = sct.monitors[0]

            self.vleft = monitor["left"]
            self.vtop = monitor["top"]
            self.vwidth = monitor["width"]
            self.vheight = monitor["height"]

            shot = sct.grab(
                monitor
            )

            self.background = image_from_mss_shot(
                shot
            )

        # ----------------------------------------------------
        # 全画面overlay
        # ----------------------------------------------------

        self.overlay = tk.Toplevel(
            root
        )

        self.overlay.overrideredirect(
            True
        )

        self.overlay.attributes(
            "-topmost",
            True
        )

        self.overlay.attributes(
            "-alpha",
            0.28
        )

        self.overlay.configure(
            bg="black"
        )

        self.overlay.geometry(
            f"{self.vwidth}x{self.vheight}"
            f"{self.vleft:+d}"
            f"{self.vtop:+d}"
        )

        self.canvas = tk.Canvas(
            self.overlay,
            bg="black",
            highlightthickness=0,
            cursor="crosshair"
        )

        self.canvas.pack(
            fill="both",
            expand=True
        )

        self.canvas.bind(
            "<ButtonPress-1>",
            self.on_press
        )

        self.canvas.bind(
            "<B1-Motion>",
            self.on_drag
        )

        self.canvas.bind(
            "<ButtonRelease-1>",
            self.on_release
        )

        self.canvas.bind(
            "<Motion>",
            self.on_motion
        )

        self.canvas.bind(
            "<Button-3>",
            lambda _e:
                self.cancel()
        )

        self.overlay.bind(
            "<Escape>",
            lambda _e:
                self.cancel()
        )

        # ----------------------------------------------------
        # 拡大鏡
        # ----------------------------------------------------

        self.mag = tk.Toplevel()

        self.mag.overrideredirect(
            True
        )

        self.mag.attributes(
            "-topmost",
            True
        )

        self.mag.configure(
            bg="white",
            padx=2,
            pady=2
        )

        self.mag_label = tk.Label(
            self.mag,
            bd=0,
            cursor="fleur"
        )

        self.mag_label.pack()

        self.coord_label = tk.Label(
            self.mag,
            text="",
            bg="white",
            fg="black",
            font=(
                "Segoe UI",
                9
            ),
            cursor="fleur"
        )

        self.coord_label.pack(
            fill="x"
        )

        self.overlay.focus_force()


    # ========================================================
    # 選択開始
    # ========================================================

    def on_press(
        self,
        event
    ):
        self.start_x = (
            event.x_root
        )

        self.start_y = (
            event.y_root
        )

        x = (
            event.x_root
            - self.vleft
        )

        y = (
            event.y_root
            - self.vtop
        )

        if self.rect_id is not None:
            self.canvas.delete(
                self.rect_id
            )

        self.rect_id = (
            self.canvas.create_rectangle(
                x,
                y,
                x,
                y,
                outline="red",
                width=3
            )
        )


    # ========================================================
    # ドラッグ
    # ========================================================

    def on_drag(
        self,
        event
    ):
        if self.start_x is None:
            return

        x1 = (
            self.start_x
            - self.vleft
        )

        y1 = (
            self.start_y
            - self.vtop
        )

        x2 = (
            event.x_root
            - self.vleft
        )

        y2 = (
            event.y_root
            - self.vtop
        )

        self.canvas.coords(
            self.rect_id,
            x1,
            y1,
            x2,
            y2
        )


    # ========================================================
    # 選択確定
    # ========================================================

    def on_release(
        self,
        event
    ):
        if self.start_x is None:
            return

        x1 = min(
            self.start_x,
            event.x_root
        )

        y1 = min(
            self.start_y,
            event.y_root
        )

        x2 = max(
            self.start_x,
            event.x_root
        )

        y2 = max(
            self.start_y,
            event.y_root
        )

        width = x2 - x1
        height = y2 - y1

        if (
            width < 2
            or height < 2
        ):
            return

        self.close()

        self.callback(
            x1,
            y1,
            width,
            height
        )


    # ========================================================
    # 拡大鏡
    # ========================================================

    def on_motion(
        self,
        event
    ):
        gx = event.x_root
        gy = event.y_root

        px = gx - self.vleft
        py = gy - self.vtop

        r = self.MAG_RADIUS

        left = max(
            0,
            px - r
        )

        top = max(
            0,
            py - r
        )

        right = min(
            self.vwidth,
            px + r + 1
        )

        bottom = min(
            self.vheight,
            py + r + 1
        )

        crop = (
            self.background.crop(
                (
                    left,
                    top,
                    right,
                    bottom
                )
            )
        )

        crop = crop.resize(
            (
                crop.width
                * self.MAG_SCALE,

                crop.height
                * self.MAG_SCALE
            ),
            Image.Resampling.NEAREST
        )

        # ----------------------------------------------------
        # 拡大鏡中央のcrosshair
        # ----------------------------------------------------

        draw = ImageDraw.Draw(
            crop
        )

        cx = (
            (px - left)
            * self.MAG_SCALE
            + self.MAG_SCALE // 2
        )

        cy = (
            (py - top)
            * self.MAG_SCALE
            + self.MAG_SCALE // 2
        )

        draw.line(
            (
                cx,
                0,
                cx,
                crop.height
            ),
            fill="red",
            width=1
        )

        draw.line(
            (
                0,
                cy,
                crop.width,
                cy
            ),
            fill="red",
            width=1
        )

        self.photo = (
            ImageTk.PhotoImage(
                crop
            )
        )

        self.mag_label.configure(
            image=self.photo
        )

        self.coord_label.configure(
            text=f"X={gx}   Y={gy}"
        )

        # ----------------------------------------------------
        # 拡大鏡をmouse横へ表示
        # ----------------------------------------------------

        mw = crop.width + 4
        mh = crop.height + 28

        mx = gx + 24
        my = gy + 24

        if (
            mx + mw
            > self.vleft
            + self.vwidth
        ):
            mx = (
                gx
                - mw
                - 24
            )

        if (
            my + mh
            > self.vtop
            + self.vheight
        ):
            my = (
                gy
                - mh
                - 24
            )

        self.mag.geometry(
            f"{mx:+d}{my:+d}"
        )


    def cancel(self):
        self.close()


    def close(self):

        try:
            self.mag.destroy()
        except Exception:
            pass

        try:
            self.overlay.destroy()
        except Exception:
            pass


# ============================================================
# メインGUI
# ============================================================

class LiveRegionSelector:

    MAG_RADIUS = 14
    MAG_SCALE = 10

    def __init__(
        self,
        root,
        callback,
        value_vars,
        input_mode_var,
        base_rect=None,
        target_label="",
        close_callback=None
    ):
        self.root = root
        self.callback = callback
        self.value_vars = value_vars
        self.input_mode_var = input_mode_var
        self.base_rect = base_rect
        self.target_label = target_label
        self.close_callback = close_callback
        self.closed = False
        self.root_was_topmost = False

        try:
            self.root_was_topmost = bool(
                int(root.attributes("-topmost"))
            )
        except Exception:
            self.root_was_topmost = False

        self.start_x = None
        self.start_y = None
        self.dragging = False
        self.suspend_var_events = False

        self.rect_id = None
        self.rect_text_id = None
        self.photo = None
        self.background_photo = None
        self.trace_tokens = []
        self.key_bindings = []
        self.mag_drag_start = None
        self.mag_x = None
        self.mag_y = None
        self.original_values = {
            key: var.get()
            for key, var in self.value_vars.items()
        }

        if self.base_rect is None:
            self.base_left = 0
            self.base_top = 0
            self.base_width = 0
            self.base_height = 0
        else:
            (
                self.base_left,
                self.base_top,
                self.base_width,
                self.base_height,
            ) = self.base_rect

        self.monitor_views = []

        with mss.MSS() as sct:

            virtual_monitor = sct.monitors[0]

            self.vleft = virtual_monitor["left"]
            self.vtop = virtual_monitor["top"]
            self.vwidth = virtual_monitor["width"]
            self.vheight = virtual_monitor["height"]

            monitors = (
                sct.monitors[1:]
                or [virtual_monitor]
            )

            for index, monitor in enumerate(monitors):
                self.create_monitor_view(
                    root,
                    sct,
                    monitor,
                    show_help=(index == 0)
                )

        self.draw_base_rect()

        self.mag = tk.Toplevel()

        self.mag.overrideredirect(
            True
        )

        self.mag.attributes(
            "-topmost",
            True
        )

        self.mag.configure(
            bg="white",
            padx=2,
            pady=2
        )

        self.mag_label = tk.Label(
            self.mag,
            bd=0,
            cursor="fleur"
        )

        self.mag_label.pack()

        self.coord_label = tk.Label(
            self.mag,
            text="",
            bg="white",
            fg="black",
            font=(
                "Segoe UI",
                9
            ),
            cursor="fleur"
        )

        self.coord_label.pack(
            fill="x"
        )

        self.bind_magnifier_drag(
            self.mag
        )
        self.bind_magnifier_drag(
            self.mag_label
        )
        self.bind_magnifier_drag(
            self.coord_label
        )

        self.panel = tk.Toplevel(
            root
        )

        self.panel.title(
            "\u7bc4\u56f2\u30d7\u30ec\u30d3\u30e5\u30fc"
        )

        self.panel.attributes(
            "-topmost",
            True
        )

        self.panel.withdraw()

        self.panel.protocol(
            "WM_DELETE_WINDOW",
            self.cancel
        )

        controls = ttk.Frame(
            self.panel,
            padding=12
        )

        controls.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            controls,
            text=(
                "\u6570\u5024\u5165\u529b\u3068\u30c9\u30e9\u30c3\u30b0\u3092"
                "\u540c\u6642\u306b\u4f7f\u3048\u307e\u3059"
            )
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(0, 8)
        )

        labels = [
            ("X", "x"),
            ("Y", "y"),
            ("W", "w"),
            ("H", "h"),
        ]

        for index, (label, key) in enumerate(labels):
            ttk.Label(
                controls,
                text=label
            ).grid(
                row=1,
                column=index,
                sticky="w"
            )

            minimum = -100000 if key in {"x", "y"} else 1

            ttk.Spinbox(
                controls,
                textvariable=self.value_vars[key],
                from_=minimum,
                to=100000,
                increment=1,
                width=10,
                justify="center"
            ).grid(
                row=2,
                column=index,
                padx=(0, 8),
                pady=(2, 8)
            )

        self.mode_label = ttk.Label(
            controls,
            text=""
        )

        self.mode_label.grid(
            row=3,
            column=0,
            columnspan=4,
            sticky="w"
        )

        self.selection_label = ttk.Label(
            controls,
            text=""
        )

        self.selection_label.grid(
            row=4,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(4, 10)
        )

        buttons = ttk.Frame(
            controls
        )

        buttons.grid(
            row=5,
            column=0,
            columnspan=4,
            sticky="e"
        )

        ttk.Button(
            buttons,
            text="\u78ba\u5b9a",
            command=self.apply
        ).grid(
            row=0,
            column=0,
            padx=(0, 8)
        )

        ttk.Button(
            buttons,
            text="\u30ad\u30e3\u30f3\u30bb\u30eb",
            command=self.cancel
        ).grid(
            row=0,
            column=1
        )

        self.panel.bind(
            "<Escape>",
            self.on_cancel_key
        )

        self.panel.bind(
            "<Return>",
            self.on_confirm_key
        )

        self.bind_variable_traces()
        self.bind_selector_keys()
        self.redraw_from_vars()
        self.position_panel()
        if self.monitor_views:
            self.monitor_views[0]["overlay"].focus_force()
        self.keep_root_front()


    def create_monitor_view(
        self,
        root,
        sct,
        monitor,
        show_help=False
    ):
        shot = sct.grab(
            monitor
        )

        background = image_from_mss_shot(
            shot
        )

        overlay = tk.Toplevel(
            root
        )

        overlay.overrideredirect(
            True
        )

        overlay.attributes(
            "-topmost",
            True
        )

        left = monitor["left"]
        top = monitor["top"]
        width = monitor["width"]
        height = monitor["height"]

        overlay.geometry(
            f"{width}x{height}"
            f"{left:+d}"
            f"{top:+d}"
        )

        move_toplevel_absolute(
            overlay,
            left,
            top,
            width,
            height
        )

        canvas = tk.Canvas(
            overlay,
            width=width,
            height=height,
            highlightthickness=0,
            cursor="crosshair"
        )

        canvas.pack(
            fill="both",
            expand=True
        )

        photo = ImageTk.PhotoImage(
            background
        )

        canvas.create_image(
            0,
            0,
            anchor="nw",
            image=photo
        )

        if show_help:
            canvas.create_text(
                16,
                16,
                anchor="nw",
                fill="white",
                text=(
                    "\u30c9\u30e9\u30c3\u30b0\u3067\u9078\u629e / "
                    "Enter\u3067\u78ba\u5b9a / Esc\u3067\u30ad\u30e3\u30f3\u30bb\u30eb"
                ),
                font=("Segoe UI", 11, "bold")
            )

        view = {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "overlay": overlay,
            "canvas": canvas,
            "background": background,
            "photo": photo,
            "rect_id": None,
            "text_id": None,
        }

        canvas._region_selector_view = view

        canvas.bind(
            "<ButtonPress-1>",
            self.on_press
        )

        canvas.bind(
            "<B1-Motion>",
            self.on_drag
        )

        canvas.bind(
            "<ButtonRelease-1>",
            self.on_release
        )

        canvas.bind(
            "<Motion>",
            self.on_motion
        )

        canvas.bind(
            "<Button-3>",
            lambda _e:
                self.cancel()
        )

        overlay.bind(
            "<Escape>",
            self.on_cancel_key
        )

        overlay.bind(
            "<Return>",
            self.on_confirm_key
        )

        self.monitor_views.append(
            view
        )


    def draw_base_rect(self):
        if (
            self.base_rect is None
            or self.base_width <= 0
            or self.base_height <= 0
        ):
            return

        for view in self.monitor_views:
            coords = self.rect_to_view_coords(
                view,
                self.base_left,
                self.base_top,
                self.base_width,
                self.base_height
            )

            if coords is None:
                continue

            x1, y1, x2, y2 = coords

            view["canvas"].create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline="#00c8ff",
                width=2,
                dash=(7, 4)
            )

            view["canvas"].create_text(
                x1 + 8,
                y1 + 8,
                anchor="nw",
                fill="#00c8ff",
                text=(
                    "\u57fa\u6e96\u30a6\u30a3\u30f3\u30c9\u30a6"
                    if not self.target_label
                    else self.target_label
                ),
                font=("Segoe UI", 10, "bold")
            )


    def rect_to_view_coords(
        self,
        view,
        left,
        top,
        width,
        height
    ):
        right = left + width
        bottom = top + height

        view_left = view["left"]
        view_top = view["top"]
        view_right = view_left + view["width"]
        view_bottom = view_top + view["height"]

        clip_left = max(
            left,
            view_left
        )
        clip_top = max(
            top,
            view_top
        )
        clip_right = min(
            right,
            view_right
        )
        clip_bottom = min(
            bottom,
            view_bottom
        )

        if (
            clip_right <= clip_left
            or clip_bottom <= clip_top
        ):
            return None

        return (
            clip_left - view_left,
            clip_top - view_top,
            clip_right - view_left,
            clip_bottom - view_top,
        )


    def bind_variable_traces(self):
        for var in self.value_vars.values():
            token = var.trace_add(
                "write",
                self.on_var_changed
            )
            self.trace_tokens.append(
                (var, token)
            )


    def bind_selector_keys(self):
        widgets = [
            self.root,
            self.mag,
        ]

        for widget in widgets:
            try:
                return_id = widget.bind(
                    "<Return>",
                    self.on_confirm_key,
                    add="+"
                )
                escape_id = widget.bind(
                    "<Escape>",
                    self.on_cancel_key,
                    add="+"
                )
                self.key_bindings.append(
                    (
                        widget,
                        "<Return>",
                        return_id
                    )
                )
                self.key_bindings.append(
                    (
                        widget,
                        "<Escape>",
                        escape_id
                    )
                )
            except Exception:
                pass


    def unbind_selector_keys(self):
        for widget, sequence, bind_id in self.key_bindings:
            try:
                widget.unbind(
                    sequence,
                    bind_id
                )
            except Exception:
                pass

        self.key_bindings.clear()


    def on_confirm_key(
        self,
        _event=None
    ):
        self.apply()
        return "break"


    def on_cancel_key(
        self,
        _event=None
    ):
        self.cancel()
        return "break"


    def bind_magnifier_drag(
        self,
        widget
    ):
        widget.bind(
            "<ButtonPress-1>",
            self.on_mag_drag_start,
            add="+"
        )
        widget.bind(
            "<B1-Motion>",
            self.on_mag_drag,
            add="+"
        )


    def on_mag_drag_start(
        self,
        event
    ):
        self.mag_drag_start = (
            event.x_root,
            event.y_root,
            self.mag_x
            if self.mag_x is not None
            else self.mag.winfo_rootx(),
            self.mag_y
            if self.mag_y is not None
            else self.mag.winfo_rooty(),
        )
        return "break"


    def on_mag_drag(
        self,
        event
    ):
        if self.mag_drag_start is None:
            return "break"

        start_x, start_y, base_x, base_y = self.mag_drag_start

        self.mag_x = base_x + (
            event.x_root
            - start_x
        )
        self.mag_y = base_y + (
            event.y_root
            - start_y
        )

        self.position_magnifier()

        return "break"


    def lift(self):
        for view in self.monitor_views:
            try:
                view["overlay"].lift()
                view["overlay"].attributes(
                    "-topmost",
                    True
                )
            except Exception:
                pass

        try:
            self.mag.lift()
            self.mag.attributes(
                "-topmost",
                True
            )
        except Exception:
            pass

        self.keep_root_front()


    def keep_root_front(self):
        try:
            self.root.attributes(
                "-topmost",
                True
            )
            self.root.lift()
        except Exception:
            pass


    def unbind_variable_traces(self):
        for var, token in self.trace_tokens:
            try:
                var.trace_remove(
                    "write",
                    token
                )
            except Exception:
                pass

        self.trace_tokens.clear()


    def position_panel(self):
        self.panel.update_idletasks()

        panel_width = self.panel.winfo_width()
        panel_height = self.panel.winfo_height()

        panel_x = (
            self.root.winfo_rootx()
            + self.root.winfo_width()
            + 20
        )

        panel_y = self.root.winfo_rooty()

        if panel_x + panel_width > self.vleft + self.vwidth:
            panel_x = (
                self.root.winfo_rootx()
                - panel_width
                - 20
            )

        if panel_y + panel_height > self.vtop + self.vheight:
            panel_y = (
                self.vtop
                + self.vheight
                - panel_height
                - 20
            )

        panel_x = max(
            self.vleft + 20,
            panel_x
        )

        panel_y = max(
            self.vtop + 20,
            panel_y
        )

        move_toplevel_absolute(
            self.panel,
            panel_x,
            panel_y,
            panel_width,
            panel_height
        )


    def values_to_screen_region(
        self,
        a,
        b,
        c,
        d
    ):
        mode = self.input_mode_var.get()

        if mode == "center_abs":
            left_abs = abs(a)
            top_abs = abs(b)
            right_abs = abs(c)
            bottom_abs = abs(d)

            if self.base_rect is None:
                center_x = self.vleft + (self.vwidth / 2)
                center_y = self.vtop + (self.vheight / 2)
            else:
                center_x = self.base_left + (self.base_width / 2)
                center_y = self.base_top + (self.base_height / 2)

            left = int(round(center_x - left_abs))
            top = int(round(center_y - top_abs))
            right = int(round(center_x + right_abs))
            bottom = int(round(center_y + bottom_abs))

            return (
                left,
                top,
                right - left,
                bottom - top
            )

        if mode == "size":
            return (
                a + self.base_left,
                b + self.base_top,
                c,
                d
            )

        left = min(a, c)
        top = min(b, d)
        right = max(a, c)
        bottom = max(b, d)

        return (
            left + self.base_left,
            top + self.base_top,
            right - left,
            bottom - top
        )


    def screen_to_values(
        self,
        left,
        top,
        width,
        height
    ):
        mode = self.input_mode_var.get()

        if mode == "center_abs":
            if self.base_rect is None:
                center_x = self.vleft + (self.vwidth / 2)
                center_y = self.vtop + (self.vheight / 2)
            else:
                center_x = self.base_left + (self.base_width / 2)
                center_y = self.base_top + (self.base_height / 2)

            right = left + width
            bottom = top + height

            return (
                int(round(abs(center_x - left))),
                int(round(abs(center_y - top))),
                int(round(abs(right - center_x))),
                int(round(abs(bottom - center_y)))
            )

        rel_left = left - self.base_left
        rel_top = top - self.base_top

        if mode == "size":
            return (
                rel_left,
                rel_top,
                width,
                height
            )

        return (
            rel_left,
            rel_top,
            rel_left + width,
            rel_top + height
        )


    def read_value_region(self):
        try:
            return (
                int(self.value_vars["x"].get()),
                int(self.value_vars["y"].get()),
                int(self.value_vars["w"].get()),
                int(self.value_vars["h"].get())
            )
        except ValueError:
            return None


    def read_screen_region(self):
        region = self.read_value_region()

        if region is None:
            return None

        return self.values_to_screen_region(
            *region
        )


    def event_to_screen(
        self,
        event
    ):
        view = getattr(
            event.widget,
            "_region_selector_view",
            None
        )

        if view is None:
            view = self.monitor_views[0]

        x = min(
            max(event.x, 0),
            view["width"] - 1
        )
        y = min(
            max(event.y, 0),
            view["height"] - 1
        )

        return (
            view["left"] + x,
            view["top"] + y,
            x,
            y,
            view,
        )


    def set_value_region(
        self,
        x,
        y,
        width,
        height
    ):
        self.suspend_var_events = True

        try:
            self.value_vars["x"].set(str(x))
            self.value_vars["y"].set(str(y))
            self.value_vars["w"].set(str(width))
            self.value_vars["h"].set(str(height))
        finally:
            self.suspend_var_events = False

        self.redraw_from_vars()


    def set_screen_region(
        self,
        left,
        top,
        width,
        height
    ):
        self.set_value_region(
            *self.screen_to_values(
                left,
                top,
                width,
                height
            )
        )


    def redraw_from_vars(self):
        region = self.read_screen_region()

        if region is None:
            self.selection_label.configure(
                text="\u6570\u5024\u3092\u5165\u529b\u4e2d\u3067\u3059"
            )
            return

        left, top, width, height = region

        if width <= 0 or height <= 0:
            self.selection_label.configure(
                text="W / H \u306f 1 \u4ee5\u4e0a\u3067\u6307\u5b9a"
            )
            return

        if self.input_mode_var.get() == "center_abs":
            region_values = self.read_value_region()
            if region_values is None:
                label_text = (
                    f"X={left}  Y={top}  W={width}  H={height}"
                )
            else:
                l_abs, t_abs, r_abs, b_abs = region_values
                label_text = (
                    f"L={abs(l_abs)}  T={abs(t_abs)}  "
                    f"R={abs(r_abs)}  B={abs(b_abs)}"
                )
        else:
            label_text = (
                f"X1={left}  Y1={top}  "
                f"X2={left + width}  Y2={top + height}"
            )

        text_drawn = False

        for view in self.monitor_views:
            coords = self.rect_to_view_coords(
                view,
                left,
                top,
                width,
                height
            )

            canvas = view["canvas"]

            if coords is None:
                if view["rect_id"] is not None:
                    canvas.itemconfigure(
                        view["rect_id"],
                        state="hidden"
                    )

                if view["text_id"] is not None:
                    canvas.itemconfigure(
                        view["text_id"],
                        state="hidden"
                    )

                continue

            x1, y1, x2, y2 = coords
            draw_x2 = max(
                x1,
                x2 - 1
            )
            draw_y2 = max(
                y1,
                y2 - 1
            )

            if view["rect_id"] is None:
                view["rect_id"] = canvas.create_rectangle(
                    x1,
                    y1,
                    draw_x2,
                    draw_y2,
                    outline="#ff2d55",
                    width=1,
                    dash=(1, 3)
                )
            else:
                canvas.coords(
                    view["rect_id"],
                    x1,
                    y1,
                    draw_x2,
                    draw_y2
                )
                canvas.itemconfigure(
                    view["rect_id"],
                    state="normal",
                    outline="#ff2d55",
                    width=1,
                    dash=(1, 3)
                )

            should_draw_text = (
                not text_drawn
                and (
                    view["left"] <= left < view["left"] + view["width"]
                    and view["top"] <= top < view["top"] + view["height"]
                )
            )

            if should_draw_text:
                text_x = x1 + 8
                text_y = max(
                    8,
                    y1 - 24
                )

                if view["text_id"] is None:
                    view["text_id"] = canvas.create_text(
                        text_x,
                        text_y,
                        anchor="nw",
                        fill="#ff2d55",
                        text=label_text,
                        font=("Segoe UI", 10, "bold")
                    )
                else:
                    canvas.coords(
                        view["text_id"],
                        text_x,
                        text_y
                    )
                    canvas.itemconfigure(
                        view["text_id"],
                        text=label_text,
                        state="normal"
                    )

                text_drawn = True
            elif view["text_id"] is not None:
                canvas.itemconfigure(
                    view["text_id"],
                    state="hidden"
                )

        if not text_drawn:
            for view in self.monitor_views:
                if view["rect_id"] is not None:
                    coords = view["canvas"].coords(
                        view["rect_id"]
                    )

                    if coords:
                        x1, y1, _x2, _y2 = coords

                        if view["text_id"] is None:
                            view["text_id"] = view["canvas"].create_text(
                                x1 + 8,
                                max(8, y1 - 24),
                                anchor="nw",
                                fill="#ff2d55",
                                text=label_text,
                                font=("Segoe UI", 10, "bold")
                            )
                        else:
                            view["canvas"].coords(
                                view["text_id"],
                                x1 + 8,
                                max(8, y1 - 24)
                            )
                            view["canvas"].itemconfigure(
                                view["text_id"],
                                text=label_text,
                                state="normal"
                            )

                        break

        value_region = self.read_value_region()

        if self.base_rect is None:
            self.mode_label.configure(
                text="\u5ea7\u6a19\u57fa\u6e96: \u30b9\u30af\u30ea\u30fc\u30f3\u7d76\u5bfe"
            )
            self.selection_label.configure(
                text=label_text
            )
        else:
            rel_x, rel_y, rel_c, rel_d = value_region
            self.mode_label.configure(
                text=(
                    "\u5ea7\u6a19\u57fa\u6e96: "
                    f"{self.target_label or 'target window'} "
                    f"({self.base_left}, {self.base_top})"
                )
            )
            self.selection_label.configure(
                text=(
                    f"\u5165\u529b {rel_x}, {rel_y}, "
                    f"{rel_c}, {rel_d}"
                )
            )


    def on_press(
        self,
        event
    ):
        screen_x, screen_y, _local_x, _local_y, _view = (
            self.event_to_screen(event)
        )

        self.start_x = screen_x
        self.start_y = screen_y
        self.dragging = True

        self.set_screen_region(
            screen_x,
            screen_y,
            1,
            1
        )


    def on_drag(
        self,
        event
    ):
        if not self.dragging:
            return

        screen_x, screen_y, _local_x, _local_y, _view = (
            self.event_to_screen(event)
        )

        left = min(
            self.start_x,
            screen_x
        )

        top = min(
            self.start_y,
            screen_y
        )

        width = max(
            1,
            abs(
                screen_x
                - self.start_x
            )
        )

        height = max(
            1,
            abs(
                screen_y
                - self.start_y
            )
        )

        self.set_screen_region(
            left,
            top,
            width,
            height
        )


    def on_release(
        self,
        event
    ):
        if not self.dragging:
            return

        self.on_drag(event)
        self.dragging = False


    def on_motion(
        self,
        event
    ):
        gx, gy, px, py, view = (
            self.event_to_screen(event)
        )

        r = self.MAG_RADIUS

        left = max(
            0,
            px - r
        )

        top = max(
            0,
            py - r
        )

        right = min(
            view["width"],
            px + r + 1
        )

        bottom = min(
            view["height"],
            py + r + 1
        )

        if right <= left:
            right = min(
                view["width"],
                left + 1
            )

        if bottom <= top:
            bottom = min(
                view["height"],
                top + 1
            )

        crop = view["background"].crop(
            (
                left,
                top,
                right,
                bottom
            )
        )

        crop = crop.resize(
            (
                crop.width
                * self.MAG_SCALE,
                crop.height
                * self.MAG_SCALE
            ),
            Image.Resampling.NEAREST
        )

        draw = ImageDraw.Draw(
            crop
        )

        cx = (
            (px - left)
            * self.MAG_SCALE
            + self.MAG_SCALE // 2
        )

        cy = (
            (py - top)
            * self.MAG_SCALE
            + self.MAG_SCALE // 2
        )

        draw.line(
            (
                cx,
                0,
                cx,
                crop.height
            ),
            fill="red",
            width=1
        )

        draw.line(
            (
                0,
                cy,
                crop.width,
                cy
            ),
            fill="red",
            width=1
        )

        self.photo = ImageTk.PhotoImage(
            crop
        )

        self.mag_label.configure(
            image=self.photo
        )

        self.coord_label.configure(
            text=self.format_coord_text(
                gx,
                gy
            )
        )

        self.position_magnifier()


    def format_coord_text(
        self,
        x,
        y
    ):
        if self.base_rect is None:
            return f"X={x}   Y={y}"

        return (
            f"Abs X={x} Y={y}   "
            f"Rel X={x - self.base_left} Y={y - self.base_top}"
        )


    def position_magnifier(self):
        self.mag.update_idletasks()

        width = self.mag.winfo_width()
        height = self.mag.winfo_height()

        if width <= 1:
            width = self.mag.winfo_reqwidth()

        if height <= 1:
            height = self.mag.winfo_reqheight()

        if self.mag_x is None or self.mag_y is None:
            self.mag_x = (
                self.root.winfo_rootx()
                + self.root.winfo_width()
                + 16
            )
            self.mag_y = self.root.winfo_rooty()

        max_x = (
            self.vleft
            + self.vwidth
            - width
        )
        max_y = (
            self.vtop
            + self.vheight
            - height
        )

        self.mag_x = max(
            self.vleft,
            min(
                self.mag_x,
                max_x
            )
        )
        self.mag_y = max(
            self.vtop,
            min(
                self.mag_y,
                max_y
            )
        )

        move_toplevel_absolute(
            self.mag,
            self.mag_x,
            self.mag_y,
            width,
            height
        )

        try:
            self.mag.lift()
            self.mag.attributes(
                "-topmost",
                True
            )
        except Exception:
            pass


    def on_var_changed(
        self,
        *_args
    ):
        if self.suspend_var_events:
            return

        self.redraw_from_vars()


    def restore_original_values(self):
        self.suspend_var_events = True

        try:
            for key, value in self.original_values.items():
                self.value_vars[key].set(value)
        finally:
            self.suspend_var_events = False


    def apply(self):
        value_region = self.read_value_region()
        screen_region = self.read_screen_region()

        if value_region is None or screen_region is None:
            messagebox.showerror(
                "\u5165\u529b\u30a8\u30e9\u30fc",
                "\u7bc4\u56f2\u306e\u6570\u5024\u3092\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044",
                parent=self.root
            )
            return

        _left, _top, width, height = screen_region

        if width <= 0 or height <= 0:
            messagebox.showerror(
                "\u5165\u529b\u30a8\u30e9\u30fc",
                "W / H \u306f 1 \u4ee5\u4e0a\u3067\u6307\u5b9a\u3057\u3066\u304f\u3060\u3055\u3044",
                parent=self.root
            )
            return

        self.close()
        self.callback(
            *value_region
        )


    def cancel(self):
        self.restore_original_values()
        self.close()


    def close(self):
        if self.closed:
            return

        self.closed = True
        self.unbind_selector_keys()
        self.unbind_variable_traces()

        try:
            self.mag.destroy()
        except Exception:
            pass

        for view in self.monitor_views:
            try:
                view["overlay"].destroy()
            except Exception:
                pass

        try:
            self.panel.destroy()
        except Exception:
            pass

        try:
            self.root.attributes(
                "-topmost",
                self.root_was_topmost
            )
        except Exception:
            pass

        if self.close_callback is not None:
            self.close_callback()


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

        main = ttk.Frame(
            self.root,
            padding=18
        )

        main.pack(
            fill="both",
            expand=True
        )

        main.columnconfigure(
            0,
            weight=1
        )


        # ====================================================
        # 保存先
        # ====================================================

        save_frame = ttk.LabelFrame(
            main,
            text="保存先",
            padding=12
        )

        save_frame.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 10)
        )

        save_frame.columnconfigure(
            0,
            weight=1
        )

        ttk.Entry(
            save_frame,
            textvariable=
                self.output_dir
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 8)
        )

        ttk.Button(
            save_frame,
            text="参照",
            command=
                self.choose_output
        ).grid(
            row=0,
            column=1
        )


        # ====================================================
        # 撮影領域
        # ====================================================

        region = ttk.LabelFrame(
            main,
            text="撮影領域",
            padding=12
        )

        region.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(0, 10)
        )

        region_values = [
            (
                self.region_label_vars[0],
                self.region_x
            ),
            (
                self.region_label_vars[1],
                self.region_y
            ),
            (
                self.region_label_vars[2],
                self.region_w
            ),
            (
                self.region_label_vars[3],
                self.region_h
            )
        ]

        for i, (
            label_var,
            variable
        ) in enumerate(
            region_values
        ):

            ttk.Label(
                region,
                textvariable=label_var
            ).grid(
                row=0,
                column=i * 2,
                padx=(0, 4)
            )

            ttk.Spinbox(
                region,
                textvariable=variable,
                from_=-100000,
                to=100000,
                increment=1,
                width=9,
                justify="center"
            ).grid(
                row=0,
                column=
                    i * 2 + 1,
                padx=(0, 10)
            )

        ttk.Label(
            region,
            text="input mode"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        ttk.Combobox(
            region,
            textvariable=self.region_input_mode,
            values=(
                "corners",
                "center_abs"
            ),
            state="readonly",
            width=14
        ).grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="w",
            pady=(10, 0)
        )

        ttk.Checkbutton(
            region,
            text="\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u3092\u57fa\u6e96\u306b\u3059\u308b",
            variable=self.relative_to_window,
            command=self.on_region_mode_changed
        ).grid(
            row=2,
            column=0,
            columnspan=8,
            sticky="w",
            pady=(10, 0)
        )

        ttk.Button(
            region,
            text="画面から範囲指定",
            command=
                self.prepare_region_select
        ).grid(
            row=3,
            column=0,
            columnspan=8,
            pady=(12, 0)
        )

        ttk.Label(
            region,
            text=(
                "ドラッグ中はカーソル周辺を拡大表示。"
                "確定後はX / Y / 幅 / 高さを"
                "1px単位で調整できます。"
            )
        ).grid(
            row=4,
            column=0,
            columnspan=8,
            pady=(8, 0)
        )

        ttk.Label(
            region,
            textvariable=self.region_summary,
            justify="left"
        ).grid(
            row=5,
            column=0,
            columnspan=8,
            sticky="w",
            pady=(6, 0)
        )


        # ====================================================
        # ページ制御
        # ====================================================

        page = ttk.LabelFrame(
            main,
            text="ページ制御",
            padding=12
        )

        page.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(0, 10)
        )

        ttk.Label(
            page,
            text="ページ送りキー"
        ).grid(
            row=0,
            column=0,
            sticky="w"
        )

        ttk.Entry(
            page,
            textvariable=
                self.page_key,
            state="readonly",
            width=15
        ).grid(
            row=0,
            column=1,
            padx=(8, 8)
        )

        ttk.Button(
            page,
            text="キー入力で設定",
            command=
                self.capture_page_key
        ).grid(
            row=0,
            column=2
        )


        ttk.Label(
            page,
            text="開始ページ"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        ttk.Spinbox(
            page,
            textvariable=
                self.start_page,
            from_=1,
            to=999999,
            width=10
        ).grid(
            row=1,
            column=1,
            sticky="w",
            padx=(8, 0),
            pady=(10, 0)
        )


        ttk.Label(
            page,
            text="終了ページ"
        ).grid(
            row=1,
            column=2,
            sticky="w",
            padx=(20, 0),
            pady=(10, 0)
        )

        ttk.Spinbox(
            page,
            textvariable=
                self.end_page,
            from_=1,
            to=999999,
            width=10
        ).grid(
            row=1,
            column=3,
            sticky="w",
            padx=(8, 0),
            pady=(10, 0)
        )


        ttk.Label(
            page,
            text="現在ページ"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        ttk.Spinbox(
            page,
            textvariable=
                self.current_page,
            from_=1,
            to=999999,
            width=10
        ).grid(
            row=2,
            column=1,
            sticky="w",
            padx=(8, 0),
            pady=(10, 0)
        )


        # ====================================================
        # timing
        # ====================================================

        timing = ttk.LabelFrame(
            main,
            text="タイミング",
            padding=12
        )

        timing.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(0, 10)
        )

        ttk.Label(
            timing,
            text="撮影後待機 (ms)"
        ).grid(
            row=0,
            column=0,
            sticky="w"
        )

        ttk.Spinbox(
            timing,
            textvariable=
                self.capture_delay,
            from_=0,
            to=60000,
            width=10
        ).grid(
            row=0,
            column=1,
            padx=(8, 25)
        )


        ttk.Label(
            timing,
            text=
                "ページ送り後待機 (ms)"
        ).grid(
            row=0,
            column=2,
            sticky="w"
        )

        ttk.Spinbox(
            timing,
            textvariable=
                self.page_delay,
            from_=0,
            to=60000,
            width=10
        ).grid(
            row=0,
            column=3,
            padx=(8, 0)
        )


        # ====================================================
        # 保存形式
        # ====================================================

        naming = ttk.LabelFrame(
            main,
            text="保存形式",
            padding=12
        )

        naming.grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(0, 10)
        )

        ttk.Label(
            naming,
            text="ファイル名接頭辞"
        ).grid(
            row=0,
            column=0
        )

        ttk.Entry(
            naming,
            textvariable=
                self.prefix,
            width=20
        ).grid(
            row=0,
            column=1,
            padx=(8, 20)
        )

        ttk.Label(
            naming,
            text=(
                "PNG / compress_level=1"
                "（低圧縮・可逆）"
            )
        ).grid(
            row=0,
            column=2
        )

        ttk.Checkbutton(
            naming,
            text="\u65e2\u5b58\u30d5\u30a1\u30a4\u30eb\u3092\u4e0a\u66f8\u304d",
            variable=self.overwrite_existing
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0)
        )

        ttk.Label(
            naming,
            text="\u4e0a\u66f8\u304d\u3057\u306a\u3044\u5834\u5408\u306e\u63a5\u5c3e\u8f9e"
        ).grid(
            row=1,
            column=2,
            sticky="e",
            padx=(12, 8),
            pady=(8, 0)
        )

        ttk.Entry(
            naming,
            textvariable=self.filename_suffix,
            width=14
        ).grid(
            row=1,
            column=3,
            sticky="w",
            pady=(8, 0)
        )

        ttk.Label(
            naming,
            text="\u9023\u756a\u6841\u6570"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0)
        )

        ttk.Spinbox(
            naming,
            textvariable=self.filename_digits,
            from_=1,
            to=12,
            width=6
        ).grid(
            row=2,
            column=1,
            sticky="w",
            padx=(8, 20),
            pady=(8, 0)
        )

        ttk.Label(
            naming,
            text="\u4fdd\u5b58\u9023\u756a\u958b\u59cb"
        ).grid(
            row=2,
            column=2,
            sticky="e",
            padx=(12, 8),
            pady=(8, 0)
        )

        ttk.Spinbox(
            naming,
            textvariable=self.filename_start,
            from_=0,
            to=999999999,
            width=10
        ).grid(
            row=2,
            column=3,
            sticky="w",
            pady=(8, 0)
        )


        # ====================================================
        # 状態
        # ====================================================

        ttk.Label(
            main,
            textvariable=
                self.target_name
        ).grid(
            row=5,
            column=0,
            pady=(2, 4)
        )

        ttk.Label(
            main,
            textvariable=
                self.status
        ).grid(
            row=6,
            column=0,
            pady=(2, 8)
        )

        self.progress = (
            ttk.Progressbar(
                main,
                mode="determinate"
            )
        )

        self.progress.grid(
            row=7,
            column=0,
            sticky="ew",
            pady=(0, 12)
        )


        # ====================================================
        # Buttons
        # ====================================================

        buttons = ttk.Frame(
            main
        )

        buttons.grid(
            row=8,
            column=0
        )

        self.start_button = ttk.Button(
            buttons,
            text="開始",
            command=
                self.start_capture
        )

        self.start_button.grid(
            row=0,
            column=0,
            padx=5
        )

        self.pause_button = ttk.Button(
            buttons,
            text="一時停止",
            command=
                self.toggle_pause
        )

        self.pause_button.grid(
            row=0,
            column=1,
            padx=5
        )

        ttk.Button(
            buttons,
            text="停止",
            command=
                self.stop_capture
        ).grid(
            row=0,
            column=2,
            padx=5
        )

        ttk.Button(
            buttons,
            text="\u30c8\u30ea\u30df\u30f3\u30b0",
            command=
                self.open_trim_tool
        ).grid(
            row=0,
            column=3,
            padx=5
        )

        ttk.Label(
            main,
            text=
                "Esc：一時停止 / 再開"
        ).grid(
            row=9,
            column=0,
            pady=(10, 0)
        )


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
                f"legacy X={a} Y={b} W={c} H={d}"
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

            if self.stop_event.is_set():
                return "stop"

            if (
                self.pause_event.is_set()
                or generation
                != self.pause_generation
            ):
                return "restart"

            time.sleep(
                0.01
            )

        return "ok"


    def wait_until_resumed(self):

        while self.pause_event.is_set():

            if self.stop_event.is_set():
                return False

            time.sleep(
                0.03
            )

        return (
            not self.stop_event.is_set()
        )


    # ========================================================
    # 撮影Worker
    # ========================================================

    def capture_worker(self):

        try:

            with mss.MSS() as sct:

                while (
                    not
                    self.stop_event.is_set()
                ):

                    if not self.wait_until_resumed():
                        break

                    with self.state_lock:
                        cfg = dict(
                            self.capture_config
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
                        self.target_hwnd
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
                        self.pause_generation
                    )


                    # =========================================
                    # screenshot
                    # =========================================

                    absolute_region = (
                        self.resolve_region_values(
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
                        self.root.after(
                            0,
                            lambda:
                                self.finish_with_error(
                                    "\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u304c\u898b\u3064\u304b\u3089\u305a\u30ad\u30e3\u30d7\u30c1\u30e3\u3092\u7d9a\u884c\u3067\u304d\u307e\u305b\u3093"
                                )
                        )
                        return

                    abs_x, abs_y, _abs_w, _abs_h = absolute_region

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

                    save_region_png(
                        output_path,
                        abs_x,
                        abs_y,
                        width,
                        height,
                        sct=sct,
                        compress_level=1
                    )


                    self.root.after(
                        0,
                        self.update_after_capture,
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
                            and not self.is_target_active(
                                target_hwnd
                            )
                        ):
                            self.activate_target(
                                target_hwnd
                            )
                            time.sleep(
                                0.05
                            )

                        send_page_key(
                            page_key
                        )

                    except Exception as e:

                        self.root.after(
                            0,
                            lambda e=e:
                                self.finish_with_error(
                                    str(e)
                                )
                        )

                        return


                    next_page = (
                        page + 1
                    )


                    with self.state_lock:

                        self.capture_config[
                            "current_page"
                        ] = next_page


                    self.root.after(
                        0,
                        self.set_current_page,
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


            self.root.after(
                0,
                self.finish_capture
            )


        except Exception as e:

            self.root.after(
                0,
                lambda e=e:
                    self.finish_with_error(
                        str(e)
                    )
            )


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


# ============================================================
# 起動
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = CaptureApp(
        root
    )

    root.mainloop()
