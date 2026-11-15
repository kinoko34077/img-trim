import ctypes
from ctypes import wintypes


user32 = ctypes.windll.user32

SW_RESTORE = 9
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010


def enable_dpi_awareness():
    """プロセスを DPI aware にする。

    Tk と Win32 / mss の座標を揃えるため、起動直後に呼び出す。
    """

    try:
        user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4)
        )
        return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def get_toplevel_hwnd(window):
    window.update_idletasks()

    try:
        frame_id = window.wm_frame()

        if frame_id:
            return int(
                frame_id,
                0
            )
    except Exception:
        pass

    return window.winfo_id()


def move_toplevel_absolute(
    window,
    x,
    y,
    width=None,
    height=None
):
    """Tk の Toplevel を仮想スクリーン上の絶対座標へ配置する。"""

    window.update_idletasks()

    if width is None:
        width = window.winfo_width()

    if height is None:
        height = window.winfo_height()

    hwnd = get_toplevel_hwnd(
        window
    )

    user32.SetWindowPos(
        hwnd,
        0,
        int(x),
        int(y),
        int(width),
        int(height),
        SWP_NOZORDER | SWP_NOACTIVATE
    )


def get_cursor_position():
    point = wintypes.POINT()
    user32.GetCursorPos(
        ctypes.byref(point)
    )
    return (
        point.x,
        point.y,
    )


def rect_contains_point(
    rect,
    x,
    y
):
    left = rect["left"]
    top = rect["top"]
    right = left + rect["width"]
    bottom = top + rect["height"]

    return (
        left <= x < right
        and top <= y < bottom
    )


def pick_screen_monitor(
    sct,
    base_rect=None
):
    monitors = sct.monitors[1:]

    if not monitors:
        return sct.monitors[0]

    if base_rect is None:
        focus_x, focus_y = get_cursor_position()
    else:
        base_left, base_top, base_width, base_height = base_rect
        focus_x = base_left + base_width // 2
        focus_y = base_top + base_height // 2

    for monitor in monitors:
        if rect_contains_point(
            monitor,
            focus_x,
            focus_y
        ):
            return monitor

    return monitors[0]


def cursor_hint_rect():
    x, y = get_cursor_position()
    return (
        x,
        y,
        1,
        1,
    )

