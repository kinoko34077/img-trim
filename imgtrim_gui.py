from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tkinter as tk


_APP_DIR = Path(__file__).resolve().parent
_LEGACY_MODULE_NAME = "_imgtrim_legacy_gui"
_LEGACY_PATH = _APP_DIR / "img-trim.py"


def _load_legacy_module():
    module = sys.modules.get(
        _LEGACY_MODULE_NAME
    )

    if module is not None:
        return module

    spec = spec_from_file_location(
        _LEGACY_MODULE_NAME,
        _LEGACY_PATH
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Cannot load {_LEGACY_PATH}"
        )

    module = module_from_spec(
        spec
    )
    sys.modules[_LEGACY_MODULE_NAME] = module
    spec.loader.exec_module(
        module
    )

    return module


def get_trim_app_class():
    return _load_legacy_module().TrimApp


def open_trim_window(
    parent=None,
    *,
    input_dir=None,
    output_dir=None
):
    window = tk.Toplevel(
        parent
    ) if parent is not None else tk.Tk()

    app_class = get_trim_app_class()
    app = app_class(
        window
    )

    if input_dir:
        app.input_dir.set(
            str(input_dir)
        )

    if output_dir:
        app.output_dir.set(
            str(output_dir)
        )

    if parent is not None:
        window.transient(
            parent
        )
        window.lift()

    return app


def main():
    root = tk.Tk()
    get_trim_app_class()(
        root
    )
    root.mainloop()


if __name__ == "__main__":
    main()
