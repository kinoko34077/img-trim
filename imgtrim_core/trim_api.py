from dataclasses import dataclass
from pathlib import Path

from PIL import Image


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


@dataclass(frozen=True)
class TrimMargins:
    top: int
    bottom: int
    left: int
    right: int

    def validate_non_negative(self):
        if any(
            value < 0
            for value in (
                self.top,
                self.bottom,
                self.left,
                self.right,
            )
        ):
            raise ValueError(
                "トリミング量に負の値は指定できません。"
            )


@dataclass(frozen=True)
class TrimBatchItem:
    index: int
    total: int
    input_path: Path
    output_path: Path | None
    success: bool
    error: str | None = None


def collect_image_files(
    input_dir,
    output_dir,
    *,
    include_subfolders=False
):
    input_dir = Path(
        input_dir
    )
    output_dir = Path(
        output_dir
    )

    if include_subfolders:
        candidates = input_dir.rglob("*")
    else:
        candidates = input_dir.iterdir()

    files = []

    try:
        output_resolved = output_dir.resolve()
    except Exception:
        output_resolved = output_dir

    for path in candidates:
        if not path.is_file():
            continue

        if (
            path.suffix.lower()
            not in SUPPORTED_EXTENSIONS
        ):
            continue

        try:
            path.resolve().relative_to(
                output_resolved
            )
            continue
        except ValueError:
            pass

        files.append(
            path
        )

    files.sort(
        key=lambda p: str(p).lower()
    )

    return files


def build_output_path(
    input_path,
    input_dir,
    output_dir,
    *,
    include_subfolders=False
):
    input_path = Path(
        input_path
    )
    input_dir = Path(
        input_dir
    )
    output_dir = Path(
        output_dir
    )

    if include_subfolders:
        relative_path = input_path.relative_to(
            input_dir
        )
        return output_dir / relative_path

    return output_dir / input_path.name


def trim_image(
    image,
    margins
):
    if not isinstance(
        margins,
        TrimMargins
    ):
        margins = TrimMargins(
            top=margins["top"],
            bottom=margins["bottom"],
            left=margins["left"],
            right=margins["right"],
        )

    margins.validate_non_negative()

    width, height = image.size

    new_width = (
        width
        - margins.left
        - margins.right
    )
    new_height = (
        height
        - margins.top
        - margins.bottom
    )

    if (
        new_width <= 0
        or new_height <= 0
    ):
        raise ValueError(
            f"画像サイズ {width}x{height} に対して"
            "トリミング量が大きすぎます。"
        )

    return image.crop(
        (
            margins.left,
            margins.top,
            width - margins.right,
            height - margins.bottom,
        )
    )


def save_trimmed_image(
    image,
    output_path
):
    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if (
        output_path.suffix.lower()
        in {".jpg", ".jpeg"}
        and image.mode in {"RGBA", "LA", "P"}
    ):
        image = image.convert(
            "RGB"
        )

    image.save(
        output_path
    )

    return output_path


def trim_image_to_path(
    input_path,
    output_path,
    margins
):
    with Image.open(input_path) as img:
        cropped = trim_image(
            img,
            margins
        )

        return save_trimmed_image(
            cropped,
            output_path
        )


def run_trim_batch(
    input_dir,
    output_dir,
    margins,
    *,
    include_subfolders=False,
    files=None
):
    input_dir = Path(
        input_dir
    )
    output_dir = Path(
        output_dir
    )

    if files is None:
        files = collect_image_files(
            input_dir,
            output_dir,
            include_subfolders=include_subfolders
        )

    total = len(files)

    for index, input_path in enumerate(
        files,
        start=1
    ):
        output_path = build_output_path(
            input_path,
            input_dir,
            output_dir,
            include_subfolders=include_subfolders
        )

        try:
            trim_image_to_path(
                input_path,
                output_path,
                margins
            )

            yield TrimBatchItem(
                index=index,
                total=total,
                input_path=input_path,
                output_path=output_path,
                success=True
            )

        except Exception as exc:
            yield TrimBatchItem(
                index=index,
                total=total,
                input_path=input_path,
                output_path=output_path,
                success=False,
                error=str(exc)
            )
