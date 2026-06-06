import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
from pathlib import Path
from typing import Dict

from core.converter import Converter
from core.ffmpeg_manager import (
    get_ffmpeg_path,
    get_ffprobe_path,
    get_input_dir,
    get_output_dir,
)
from core.scanner import scan_input
from gui.file_tree import CheckboxTreeview


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.input_dir = get_input_dir()
        self.output_dir = get_output_dir()
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cancel_event = None
        self.progress_queue = None
        self.worker_thread = None
        self._converting = False
        self._total_files = 0
        self._conversion_inputs = []

        self.title("FLAC → MP3 Converter")
        self.geometry("860x660")
        self.minsize(700, 500)

        self._setup_ui()
        self._reset_progress()
        self._update_ui_state("idle")

    def _setup_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 10, 10, 6))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)

        self.btn_refresh = ttk.Button(
            toolbar,
            text="Actualizar lista",
            command=self._refresh_list,
        )
        self.btn_refresh.grid(row=0, column=0, sticky="w")

        tree_frame = ttk.Frame(self, padding=(10, 0, 10, 6))
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.file_tree = CheckboxTreeview(tree_frame)
        self.file_tree.set_on_check_callback(self._update_selection_count)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.file_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        selection_frame = ttk.Frame(self, padding=(10, 0, 10, 8))
        selection_frame.grid(row=2, column=0, sticky="ew")
        selection_frame.columnconfigure(2, weight=1)

        self.btn_select_all = ttk.Button(
            selection_frame,
            text="Seleccionar todo",
            command=self.file_tree.select_all,
        )
        self.btn_select_all.grid(row=0, column=0, sticky="w")

        self.btn_deselect_all = ttk.Button(
            selection_frame,
            text="Deseleccionar todo",
            command=self.file_tree.deselect_all,
        )
        self.btn_deselect_all.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.lbl_selection_count = ttk.Label(selection_frame, text="0 archivos seleccionados")
        self.lbl_selection_count.grid(row=0, column=3, sticky="e")

        progress_frame = ttk.Frame(self, padding=(10, 0, 10, 8))
        progress_frame.grid(row=3, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.lbl_current_file = ttk.Label(progress_frame, text="Archivo actual: —")
        self.lbl_current_file.grid(row=0, column=0, sticky="w")

        file_progress_row = ttk.Frame(progress_frame)
        file_progress_row.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        file_progress_row.columnconfigure(0, weight=1)

        self.pbar_file = ttk.Progressbar(file_progress_row, maximum=100)
        self.pbar_file.grid(row=0, column=0, sticky="ew")

        self.lbl_file_pct = ttk.Label(file_progress_row, text="0%")
        self.lbl_file_pct.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.lbl_total = ttk.Label(progress_frame, text="Total: (0 / 0 archivos)")
        self.lbl_total.grid(row=2, column=0, sticky="w")

        total_progress_row = ttk.Frame(progress_frame)
        total_progress_row.grid(row=3, column=0, sticky="ew", pady=(4, 8))
        total_progress_row.columnconfigure(0, weight=1)

        self.pbar_total = ttk.Progressbar(total_progress_row, maximum=100)
        self.pbar_total.grid(row=0, column=0, sticky="ew")

        self.lbl_total_pct = ttk.Label(total_progress_row, text="0%")
        self.lbl_total_pct.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.lbl_eta = ttk.Label(progress_frame, text="⏱ —")
        self.lbl_eta.grid(row=4, column=0, sticky="w")

        buttons_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        buttons_frame.grid(row=4, column=0, sticky="ew")
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(3, weight=1)

        self.btn_convert = ttk.Button(
            buttons_frame,
            text="Convertir seleccionados",
            command=self._start_conversion,
        )
        self.btn_convert.grid(row=0, column=1, padx=(0, 8))

        self.btn_cancel = ttk.Button(
            buttons_frame,
            text="Cancelar",
            command=self._cancel_conversion,
        )
        self.btn_cancel.grid(row=0, column=2)

    def _refresh_list(self) -> None:
        nodes = scan_input(self.input_dir)
        self.file_tree.populate(nodes)
        self._total_files = len(self.file_tree._item_paths)

        if not nodes:
            self.file_tree.insert(
                "",
                "end",
                text="No se encontraron archivos FLAC en la carpeta Input/",
                values=("",),
            )
            self.file_tree.disable_checkboxes()
        else:
            self.file_tree.enable_checkboxes()

        self._reset_progress()
        self._update_selection_count()

    def _start_conversion(self) -> None:
        checked_files = self.file_tree.get_checked_files()
        if not checked_files:
            return

        self._conversion_inputs = checked_files
        file_pairs = [(path, self._build_output_path(path)) for path in checked_files]

        for path in checked_files:
            self.file_tree.set_item_status(path, "Pendiente")

        self.cancel_event = threading.Event()
        self.progress_queue = queue.Queue()
        converter = Converter(
            get_ffmpeg_path(),
            get_ffprobe_path(),
            self.cancel_event,
            self.progress_queue,
        )

        self.worker_thread = threading.Thread(
            target=converter.convert_all,
            args=(file_pairs,),
            daemon=True,
        )
        self.worker_thread.start()

        self._reset_progress(total_files=len(file_pairs))
        self._update_ui_state("converting")
        self.after(100, self._check_queue)

    def _cancel_conversion(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()
        self.btn_cancel.config(state="disabled")

    def _check_queue(self) -> None:
        if self.progress_queue is None:
            return

        try:
            while True:
                msg = self.progress_queue.get_nowait()
                self._handle_message(msg)
        except queue.Empty:
            pass

        if self._converting:
            self.after(100, self._check_queue)

    def _handle_message(self, msg: Dict) -> None:
        msg_type = msg.get("type")
        if msg_type == "progress":
            self._handle_progress(msg)
        elif msg_type == "file_done":
            self._handle_file_done(msg)
        elif msg_type == "done":
            self._handle_done(msg)

    def _handle_progress(self, msg: Dict) -> None:
        current_file = msg.get("current_file", "")
        file_percent = float(msg.get("file_percent", 0.0))
        file_index = int(msg.get("file_index", 0))
        total_files = int(msg.get("total_files", 0))

        self.lbl_current_file.config(text=f"Archivo actual: {current_file}")
        self.pbar_file["value"] = file_percent
        self.lbl_file_pct.config(text=f"{file_percent:.0f}%")
        self.lbl_total.config(text=f"Total: ({max(file_index - 1, 0)} / {total_files} archivos)")
        self._update_eta(msg.get("eta_seconds"))

    def _handle_file_done(self, msg: Dict) -> None:
        status = msg.get("status", "")
        file_index = int(msg.get("file_index", 0))
        total_files = int(msg.get("total_files", 0))

        status_labels = {
            "ok": "Convertido ✓",
            "skipped": "Omitido",
            "error": "Error ✗",
            "cancelled": "Cancelado",
        }

        if 0 < file_index <= len(self._conversion_inputs):
            path = self._conversion_inputs[file_index - 1]
            self.file_tree.set_item_status(path, status_labels.get(status, status))

        total_percent = (file_index / total_files * 100.0) if total_files else 0.0
        self.pbar_total["value"] = total_percent
        self.lbl_total_pct.config(text=f"{total_percent:.0f}%")
        self.lbl_total.config(text=f"Total: ({file_index} / {total_files} archivos)")

    def _handle_done(self, msg: Dict) -> None:
        self._update_ui_state("idle")
        self.lbl_eta.config(text="⏱ —")
        self._show_results_dialog(msg)

    def _update_ui_state(self, state: str) -> None:
        self._converting = state == "converting"

        if self._converting:
            self.btn_refresh.config(state="disabled")
            self.btn_select_all.config(state="disabled")
            self.btn_deselect_all.config(state="disabled")
            self.btn_convert.config(state="disabled")
            self.btn_cancel.config(state="normal")
            self.file_tree.disable_checkboxes()
            return

        self.btn_refresh.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.file_tree.enable_checkboxes()
        self._update_selection_count()

    def _show_results_dialog(self, msg: Dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Resultados de la conversión")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        text = scrolledtext.ScrolledText(dialog, wrap="word", state="normal")
        text.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 8))
        text.insert("1.0", self._format_results_summary(msg))
        text.config(state="disabled")

        btn_close = ttk.Button(dialog, text="Cerrar", command=dialog.destroy)
        btn_close.grid(row=1, column=0, pady=(0, 10))

    def _format_results_summary(self, msg: Dict) -> str:
        completed = int(msg.get("completed", 0))
        skipped = int(msg.get("skipped", 0))
        errors = int(msg.get("errors", 0))
        cancelled = bool(msg.get("cancelled", False))
        skipped_files = msg.get("skipped_files", [])
        error_files = msg.get("error_files", [])

        if completed > 0 and skipped == 0 and errors == 0 and not cancelled:
            return (
                "✓ ¡Conversión completada!\n"
                f"  {completed} archivo(s) convertido(s) exitosamente."
            )

        lines = [
            "=== Resultados de la conversión ===",
            "",
            f"✓ Convertidos exitosamente: {completed}",
            f"⊘ Omitidos (ya existían):   {skipped}",
            f"✗ Con errores:               {errors}",
        ]

        if skipped_files:
            lines.extend(["", "--- Archivos omitidos ---"])
            for file_name in skipped_files:
                lines.append(f"  • {file_name}")

        if error_files:
            lines.extend(["", "--- Archivos con error ---"])
            for file_name, error_msg in error_files:
                lines.append(f"  • {file_name}")
                lines.append(f"    Error: {error_msg}")

        if cancelled:
            processed = completed + skipped + errors
            cancelled_count = max(len(self._conversion_inputs) - processed, 0)
            lines.extend(["", f"--- Cancelados sin procesar: {cancelled_count} ---"])

        return "\n".join(lines)

    def _build_output_path(self, flac_path: Path) -> Path:
        relative = Path(flac_path).resolve().relative_to(self.input_dir)
        return self.output_dir / relative.with_suffix(".mp3")

    def _update_selection_count(self) -> None:
        count = self.file_tree.get_checked_count()
        self.lbl_selection_count.config(text=f"{count} archivos seleccionados")

        has_files = bool(self.file_tree._item_paths)
        idle = not self._converting
        self.btn_convert.config(state="normal" if idle and count > 0 else "disabled")
        self.btn_select_all.config(state="normal" if idle and has_files else "disabled")
        self.btn_deselect_all.config(state="normal" if idle and has_files else "disabled")

    def _reset_progress(self, total_files: int = 0) -> None:
        self.lbl_current_file.config(text="Archivo actual: —")
        self.pbar_file["value"] = 0
        self.lbl_file_pct.config(text="0%")
        self.lbl_total.config(text=f"Total: (0 / {total_files} archivos)")
        self.pbar_total["value"] = 0
        self.lbl_total_pct.config(text="0%")
        self.lbl_eta.config(text="⏱ —")

    def _update_eta(self, eta_seconds) -> None:
        if eta_seconds is None:
            self.lbl_eta.config(text="⏱ Calculando...")
            return

        mins, secs = divmod(int(eta_seconds), 60)
        if mins > 0:
            self.lbl_eta.config(text=f"⏱ Tiempo estimado: {mins} min {secs} seg")
        else:
            self.lbl_eta.config(text=f"⏱ Tiempo estimado: {secs} seg")
