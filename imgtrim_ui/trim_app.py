from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import configparser
import queue
import threading

from imgtrim_core.app_paths import application_dir
from imgtrim_ui.trim_view import build_trim_ui
from imgtrim_core.trim_api import (
    TrimMargins,
    collect_image_files,
    run_trim_batch,
)


APP_DIR = application_dir()
INI_PATH = APP_DIR / "trim_settings.ini"


class TrimApp:

    def __init__(self, root):
        self.root = root

        self.root.title("画像一括トリミング")
        self.root.geometry("650x570")
        self.root.resizable(False, False)

        # ----------------------------------------------------
        # GUI変数
        # ----------------------------------------------------

        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()

        self.top = tk.StringVar(value="0")
        self.bottom = tk.StringVar(value="0")
        self.left = tk.StringVar(value="0")
        self.right = tk.StringVar(value="0")

        self.include_subfolders = tk.BooleanVar(value=False)
        self.worker = None
        self.result_queue = queue.Queue()
        self.running = False
        self.stop_requested = False

        self.status = tk.StringVar(value="待機中")

        # ----------------------------------------------------
        # INI読込
        # ----------------------------------------------------

        self.load_settings()

        # ----------------------------------------------------
        # GUI生成
        # ----------------------------------------------------

        self.create_widgets()

        # 閉じる時に設定保存
        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )


    # ========================================================
    # GUI
    # ========================================================

    def create_widgets(self):
        build_trim_ui(self)


    # ========================================================
    # フォルダ選択
    # ========================================================

    def select_input(self):

        # 前回フォルダが存在すればそこから開く
        initial_dir = self.input_dir.get()

        if not Path(initial_dir).is_dir():
            initial_dir = str(APP_DIR)

        folder = filedialog.askdirectory(
            title="入力フォルダを選択",
            initialdir=initial_dir
        )

        if not folder:
            return

        self.input_dir.set(folder)

        # 出力先が空なら自動設定
        if not self.output_dir.get():
            self.output_dir.set(
                str(
                    Path(folder)
                    / "trimmed"
                )
            )

        self.save_settings()


    def select_output(self):

        initial_dir = self.output_dir.get()

        if not Path(initial_dir).is_dir():
            initial_dir = self.input_dir.get()

        if not Path(initial_dir).is_dir():
            initial_dir = str(APP_DIR)

        folder = filedialog.askdirectory(
            title="出力フォルダを選択",
            initialdir=initial_dir
        )

        if not folder:
            return

        self.output_dir.set(folder)

        self.save_settings()


    # ========================================================
    # INI 読込
    # ========================================================

    def load_settings(self):

        if not INI_PATH.exists():
            return

        config = configparser.ConfigParser()

        try:
            config.read(
                INI_PATH,
                encoding="utf-8"
            )

            section = config["Settings"]

            self.input_dir.set(
                section.get(
                    "input_dir",
                    ""
                )
            )

            self.output_dir.set(
                section.get(
                    "output_dir",
                    ""
                )
            )

            self.top.set(
                section.get(
                    "top",
                    "0"
                )
            )

            self.bottom.set(
                section.get(
                    "bottom",
                    "0"
                )
            )

            self.left.set(
                section.get(
                    "left",
                    "0"
                )
            )

            self.right.set(
                section.get(
                    "right",
                    "0"
                )
            )

            self.include_subfolders.set(
                section.getboolean(
                    "include_subfolders",
                    fallback=False
                )
            )

        except Exception as e:

            print(
                "INI読込エラー:",
                e
            )


    # ========================================================
    # INI 保存
    # ========================================================

    def save_settings(self):

        config = configparser.ConfigParser()

        config["Settings"] = {

            "input_dir":
                self.input_dir.get(),

            "output_dir":
                self.output_dir.get(),

            "top":
                self.top.get(),

            "bottom":
                self.bottom.get(),

            "left":
                self.left.get(),

            "right":
                self.right.get(),

            "include_subfolders":
                str(
                    self.include_subfolders.get()
                )
        }

        try:

            with open(
                INI_PATH,
                "w",
                encoding="utf-8"
            ) as file:

                config.write(file)

        except Exception as e:

            print(
                "INI保存エラー:",
                e
            )


    # ========================================================
    # 終了
    # ========================================================

    def on_close(self):

        if self.running:
            if not messagebox.askyesno(
                "???",
                "?????????????????"
            ):
                return

            self.stop_requested = True
            self.running = False

        self.save_settings()
        self.root.destroy()


    # ========================================================
    # ??????
    # ========================================================

    def get_image_files(
        self,
        input_dir,
        output_dir
    ):
        return collect_image_files(
            input_dir,
            output_dir,
            include_subfolders=self.include_subfolders.get()
        )


    # ========================================================
    # ???????: ??????
    # ========================================================

    def trim_worker(
        self,
        input_dir,
        output_dir,
        margins,
        files,
        include_subfolders
    ):
        success = 0
        errors = []

        try:
            for item in run_trim_batch(
                input_dir,
                output_dir,
                margins,
                include_subfolders=include_subfolders,
                files=files
            ):
                if self.stop_requested:
                    break

                if item.success:
                    success += 1
                else:
                    errors.append(
                        f"{item.input_path}: {item.error}"
                    )

                self.result_queue.put(
                    (
                        "progress",
                        item.index,
                        item.total
                    )
                )

        except Exception as exc:
            errors.append(str(exc))

        self.result_queue.put(
            (
                "done",
                success,
                errors,
                len(files),
                self.stop_requested
            )
        )


    def poll_trim_results(self):
        done_payload = None

        while True:
            try:
                message = self.result_queue.get_nowait()
            except queue.Empty:
                break

            kind = message[0]

            if kind == "progress":
                _kind, index, total = message
                self.progress["value"] = index
                self.status.set(
                    f"Processing {index} / {total}"
                )

            elif kind == "done":
                done_payload = message

        if done_payload is not None:
            _kind, success, errors, total, cancelled = done_payload
            self.finish_trim_run(
                success,
                errors,
                total,
                cancelled
            )
            return

        if self.running:
            self.root.after(
                50,
                self.poll_trim_results
            )


    def finish_trim_run(
        self,
        success,
        errors,
        total,
        cancelled=False
    ):
        self.running = False
        self.worker = None

        self.run_button.config(
            state="normal"
        )

        if cancelled:
            self.status.set(
                f"Cancelled {success} / {total}"
            )
            return

        self.status.set(
            f"Done {success} / {total}"
        )

        self.save_settings()

        if errors:
            error_text = "\n".join(
                errors[:10]
            )

            if len(errors) > 10:
                error_text += (
                    f"\n\n??? {len(errors) - 10} ?"
                )

            messagebox.showwarning(
                "?????????",
                f"??: {success}\n"
                f"??: {len(errors)}\n\n"
                f"{error_text}"
            )

        else:
            messagebox.showinfo(
                "??",
                f"{success} ?????????"
            )


    # ========================================================
    # ??
    # ========================================================

    def run_trim(self):

        if self.running:
            return

        try:
            input_dir = Path(
                self.input_dir.get()
            )

            output_dir = Path(
                self.output_dir.get()
            )

            top = int(
                self.top.get()
            )

            bottom = int(
                self.bottom.get()
            )

            left = int(
                self.left.get()
            )

            right = int(
                self.right.get()
            )

        except ValueError:
            messagebox.showerror(
                "?????",
                "???????????????????"
            )
            return

        margins = TrimMargins(
            top=top,
            bottom=bottom,
            left=left,
            right=right,
        )

        if not input_dir.is_dir():
            messagebox.showerror(
                "?????",
                "??????????????"
            )
            return

        if not self.output_dir.get().strip():
            messagebox.showerror(
                "?????",
                "????????????????"
            )
            return

        if any(
            value < 0
            for value in (
                top,
                bottom,
                left,
                right
            )
        ):
            messagebox.showerror(
                "?????",
                "???????????????????"
            )
            return

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.save_settings()

        files = self.get_image_files(
            input_dir,
            output_dir
        )

        if not files:
            messagebox.showinfo(
                "??",
                "???????????"
            )
            return

        self.progress["maximum"] = len(files)
        self.progress["value"] = 0
        self.status.set(
            f"Processing 0 / {len(files)}"
        )

        self.run_button.config(
            state="disabled"
        )

        self.running = True
        self.stop_requested = False
        self.result_queue = queue.Queue()
        self.worker = threading.Thread(
            target=self.trim_worker,
            args=(
                input_dir,
                output_dir,
                margins,
                files,
                self.include_subfolders.get()
            ),
            daemon=True
        )
        self.worker.start()
        self.root.after(
            50,
            self.poll_trim_results
        )



def main() -> None:
    root = tk.Tk()
    TrimApp(root)
    root.mainloop()
