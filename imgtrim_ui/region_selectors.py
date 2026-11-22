"""Screen overlays used to select and edit capture regions."""

from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from tkinter import messagebox, ttk
import mss

from imgtrim_core.app_runtime import move_toplevel_absolute
from imgtrim_core.capture_api import image_from_mss_shot


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
