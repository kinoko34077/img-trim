"""Launch the trimming screen standalone or as a child window."""

import tkinter as tk

from imgtrim_ui.trim_app import TrimApp


def get_trim_app_class():
    """Return the shared trimming screen class (legacy integration API)."""
    return TrimApp


def open_trim_window(parent=None, *, input_dir=None, output_dir=None):
    window = tk.Toplevel(parent) if parent is not None else tk.Tk()
    app = TrimApp(window)

    if input_dir:
        app.input_dir.set(str(input_dir))
    if output_dir:
        app.output_dir.set(str(output_dir))

    if parent is not None:
        window.transient(parent)
        window.lift()

    return app


def main():
    root = tk.Tk()
    TrimApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
