import ctypes
from ctypes import wintypes
from pathlib import Path

import mss
from PIL import Image

from .app_runtime import user32


def image_from_mss_shot(shot):
    return Image.frombytes(
        "RGB",
        shot.size,
        shot.bgra,
        "raw",
        "BGRX"
    )


def get_window_rect(hwnd):
    if (
        not hwnd
        or not user32.IsWindow(hwnd)
    ):
        return None

    rect = wintypes.RECT()

    if not user32.GetWindowRect(
        hwnd,
        ctypes.byref(rect)
    ):
        return None

    return (
        rect.left,
        rect.top,
        rect.right - rect.left,
        rect.bottom - rect.top,
    )


def resolve_region_absolute(
    x,
    y,
    width,
    height,
    *,
    relative_to_window=False,
    hwnd=None,
    base_rect=None
):
    if not relative_to_window:
        return (
            x,
            y,
            width,
            height,
        )

    if base_rect is None:
        base_rect = get_window_rect(
            hwnd
        )

    if base_rect is None:
        return None

    base_left, base_top, _base_width, _base_height = base_rect

    return (
        base_left + x,
        base_top + y,
        width,
        height,
    )


def grab_region_image(
    sct,
    x,
    y,
    width,
    height
):
    monitor = {
        "left": x,
        "top": y,
        "width": width,
        "height": height,
    }

    shot = sct.grab(
        monitor
    )

    return image_from_mss_shot(
        shot
    )


def save_region_png(
    output_path,
    x,
    y,
    width,
    height,
    *,
    sct=None,
    compress_level=1
):
    output_path = Path(
        output_path
    )

    owns_sct = sct is None

    if owns_sct:
        sct = mss.MSS()

    try:
        image = grab_region_image(
            sct,
            x,
            y,
            width,
            height
        )

        image.save(
            output_path,
            format="PNG",
            compress_level=compress_level
        )

        return output_path

    finally:
        if owns_sct:
            sct.close()


def resolve_output_path(
    output_path,
    *,
    overwrite=True,
    suffix="_copy"
):
    output_path = Path(
        output_path
    )

    if overwrite or not output_path.exists():
        return output_path

    suffix = (
        suffix
        if suffix
        else "_copy"
    )

    stem = output_path.stem
    extension = output_path.suffix
    parent = output_path.parent

    candidate = parent / f"{stem}{suffix}{extension}"

    if not candidate.exists():
        return candidate

    index = 2

    while True:
        candidate = parent / f"{stem}{suffix}{index}{extension}"

        if not candidate.exists():
            return candidate

        index += 1


def build_sequence_output_path(
    output_dir,
    *,
    prefix,
    page,
    start_page,
    filename_start,
    filename_digits,
    overwrite=True,
    suffix="_copy"
):
    output_dir = Path(
        output_dir
    )

    prefix = str(
        prefix
    ).replace(
        "%folder%",
        output_dir.name
    )

    sequence_number = (
        filename_start
        + (
            page
            - start_page
        )
    )

    output_path = (
        output_dir
        / (
            f"{prefix}"
            f"{sequence_number:0{filename_digits}d}"
            ".png"
        )
    )

    return resolve_output_path(
        output_path,
        overwrite=overwrite,
        suffix=suffix
    )
