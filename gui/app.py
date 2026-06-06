import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

from core import ffmpeg_manager as fm
from core import scanner
from core.converter import Converter
from gui.file_tree import CheckboxTreeview

# Mapeo de status del converter -> texto mostrado en la columna "Estado"
STATUS_TEXT = {
    "ok": "Convertido ✓",
    "skipped": "Omitido",
    "error": "Error ✗",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.input_dir: Path = fm.get_input_dir()
        self.output_dir: Path = fm.get_output_dir()
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        self.ffmpeg = fm.get_ffmpeg_path()
        self.ffprobe = fm.get_ffprobe_path()

        # Estado de conversión
        self._converting: bool = False
        self.cancel_event: threading.Event | None = None
        self.progress_queue: queue.Queue | None = None
        self.worker_thread: threading.Thread | None = None
        self._file_pairs: list[tuple[Path, Path]] = []
        self._total_files: int = 0

        self.title("FLAC → MP3 Converter")
        self.geometry("860x660")
        self.minsize(700, 500)

        self._setup_ui()
        self._update_ui_state("idle")
        self._update_selection_count()

    # ------------------------------------------------------------------ #
    # Construcción de la interfaz
    # ------------------------------------------------------------------ #
    def _setup_ui(self) -> None:
        pad = {"padx": 10, "pady": 5}

        # --- Frame toolbar ---
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x", **pad)
        self.btn_refresh = ttk.Button(toolbar, text="🔄 Actualizar lista",
                                      command=self._refresh_list)
        self.btn_refresh.pack(side="left")

        # --- Frame árbol ---
        tree_frame = ttk.Frame(self)
        tree_frame.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        self.file_tree = CheckboxTreeview(tree_frame)
        self.file_tree.frame.pack(fill="both", expand=True)
        self.file_tree.set_on_check_callback(self._update_selection_count)

        # --- Frame selección ---
        sel_frame = ttk.Frame(self)
        sel_frame.pack(side="top", fill="x", **pad)
        self.btn_select_all = ttk.Button(sel_frame, text="Seleccionar todo",
                                         command=self._select_all)
        self.btn_select_all.pack(side="left")
        self.btn_deselect_all = ttk.Button(sel_frame, text="Deseleccionar todo",
                                           command=self._deselect_all)
        self.btn_deselect_all.pack(side="left", padx=(5, 0))
        self.lbl_selection_count = ttk.Label(sel_frame, text="0 archivos seleccionados")
        self.lbl_selection_count.pack(side="right")

        # --- Frame progreso ---
        prog_frame = ttk.LabelFrame(self, text="Progreso")
        prog_frame.pack(side="top", fill="x", padx=10, pady=5)

        self.lbl_current_file = ttk.Label(prog_frame, text="Archivo actual: —")
        self.lbl_current_file.pack(anchor="w", padx=8, pady=(6, 0))

        file_row = ttk.Frame(prog_frame)
        file_row.pack(fill="x", padx=8, pady=(0, 4))
        self.pbar_file = ttk.Progressbar(file_row, orient="horizontal",
                                         mode="determinate", maximum=100)
        self.pbar_file.pack(side="left", fill="x", expand=True)
        self.lbl_file_pct = ttk.Label(file_row, text="0%", width=6, anchor="e")
        self.lbl_file_pct.pack(side="right", padx=(6, 0))

        self.lbl_total = ttk.Label(prog_frame, text="Total: (0 / 0 archivos)")
        self.lbl_total.pack(anchor="w", padx=8, pady=(6, 0))

        self.pbar_total = ttk.Progressbar(prog_frame, orient="horizontal",
                                          mode="determinate", maximum=100)
        self.pbar_total.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_eta = ttk.Label(prog_frame, text="⏱ —")
        self.lbl_eta.pack(anchor="w", padx=8, pady=(0, 6))

        # --- Frame botones ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="top", fill="x", padx=10, pady=(5, 10))
        self.btn_convert = ttk.Button(btn_frame, text="Convertir seleccionados",
                                      command=self._start_conversion)
        self.btn_convert.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.btn_cancel = ttk.Button(btn_frame, text="Cancelar",
                                     command=self._cancel_conversion)
        self.btn_cancel.pack(side="left", expand=True, fill="x", padx=(5, 0))

    # ------------------------------------------------------------------ #
    # Lista / selección
    # ------------------------------------------------------------------ #
    def _refresh_list(self) -> None:
        nodes = scanner.scan_input(self.input_dir)
        self.file_tree.populate(nodes)
        self._update_selection_count()

    def _select_all(self) -> None:
        self.file_tree.select_all()

    def _deselect_all(self) -> None:
        self.file_tree.deselect_all()

    def _update_selection_count(self) -> None:
        count = self.file_tree.get_checked_count()
        self.lbl_selection_count.config(text=f"{count} archivos seleccionados")
        if not self._converting:
            self.btn_convert.config(state="normal" if count > 0 else "disabled")

    # ------------------------------------------------------------------ #
    # Conversión
    # ------------------------------------------------------------------ #
    def _build_output_path(self, flac_path: Path) -> Path:
        relative = flac_path.relative_to(self.input_dir)
        return self.output_dir / relative.with_suffix(".mp3")

    def _start_conversion(self) -> None:
        checked = self.file_tree.get_checked_files()
        if not checked:
            return

        self._file_pairs = [(p, self._build_output_path(p)) for p in checked]
        self._total_files = len(self._file_pairs)

        self.cancel_event = threading.Event()
        self.progress_queue = queue.Queue()
        converter = Converter(self.ffmpeg, self.ffprobe,
                              self.cancel_event, self.progress_queue)

        # Reset de la UI de progreso
        self.pbar_file.config(value=0)
        self.lbl_file_pct.config(text="0%")
        self.pbar_total.config(maximum=self._total_files, value=0)
        self.lbl_total.config(text=f"Total: (0 / {self._total_files} archivos)")
        self.lbl_current_file.config(text="Archivo actual: —")
        self.lbl_eta.config(text="⏱ Calculando...")

        self._converting = True
        self._update_ui_state("converting")

        self.worker_thread = threading.Thread(
            target=converter.convert_all, args=[self._file_pairs], daemon=True)
        self.worker_thread.start()

        self.after(100, self._check_queue)

    def _cancel_conversion(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()

    def _check_queue(self) -> None:
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                self._handle_message(msg)
        except queue.Empty:
            pass
        if self._converting:
            self.after(100, self._check_queue)

    def _handle_message(self, msg: dict) -> None:
        t = msg.get("type")
        if t == "progress":
            self._handle_progress(msg)
        elif t == "file_done":
            self._handle_file_done(msg)
        elif t == "done":
            self._handle_done(msg)

    def _handle_progress(self, msg: dict) -> None:
        self.lbl_current_file.config(text=f"Archivo actual: {msg['current_file']}")
        pct = msg.get("file_percent", 0.0)
        self.pbar_file.config(value=pct)
        self.lbl_file_pct.config(text=f"{int(pct)}%")

        eta = msg.get("eta_seconds")
        if eta is None:
            self.lbl_eta.config(text="⏱ Calculando...")
        else:
            mins, secs = divmod(int(eta), 60)
            if mins > 0:
                self.lbl_eta.config(text=f"⏱ Tiempo estimado: {mins} min {secs} seg")
            else:
                self.lbl_eta.config(text=f"⏱ Tiempo estimado: {secs} seg")

    def _handle_file_done(self, msg: dict) -> None:
        idx = msg.get("file_index", 0)
        status = msg.get("status")

        # Actualizar la columna de estado del archivo correspondiente
        if 1 <= idx <= len(self._file_pairs):
            inp_path = self._file_pairs[idx - 1][0]
            self.file_tree.set_item_status(inp_path, STATUS_TEXT.get(status, "—"))

        # Progreso total
        self.pbar_total.config(value=idx)
        self.lbl_total.config(text=f"Total: ({idx} / {self._total_files} archivos)")

    def _handle_done(self, msg: dict) -> None:
        self._converting = False
        # Restaurar estado de la UI ANTES de mostrar el diálogo (modal)
        self._update_ui_state("idle")
        self.lbl_current_file.config(text="Archivo actual: —")
        self.lbl_eta.config(text="⏱ —")
        self._show_results_dialog(msg)

    def _update_ui_state(self, state: str) -> None:
        converting = (state == "converting")
        normal = "disabled" if converting else "normal"

        self.btn_refresh.config(state=normal)
        self.btn_select_all.config(state=normal)
        self.btn_deselect_all.config(state=normal)
        self.btn_cancel.config(state="normal" if converting else "disabled")

        if converting:
            self.btn_convert.config(state="disabled")
            self.file_tree.disable_checkboxes()
        else:
            self.file_tree.enable_checkboxes()
            # Convert depende de si hay selección
            count = self.file_tree.get_checked_count()
            self.btn_convert.config(state="normal" if count > 0 else "disabled")

    # ------------------------------------------------------------------ #
    # Diálogo de resultados (refinado en Tarea 10)
    # ------------------------------------------------------------------ #
    def _show_results_dialog(self, msg: dict) -> None:
        completed = msg.get("completed", 0)
        skipped = msg.get("skipped", 0)
        errors = msg.get("errors", 0)
        cancelled = msg.get("cancelled", False)
        skipped_files = msg.get("skipped_files", [])
        error_files = msg.get("error_files", [])

        text = self._format_results(
            completed, skipped, errors, cancelled, skipped_files, error_files)

        dialog = tk.Toplevel(self)
        dialog.title("Resultados de la conversión")
        dialog.geometry("500x400")
        dialog.transient(self)

        st = scrolledtext.ScrolledText(dialog, wrap="word")
        st.pack(fill="both", expand=True, padx=10, pady=10)
        st.insert("1.0", text)
        st.config(state="disabled")

        ttk.Button(dialog, text="Cerrar", command=dialog.destroy).pack(pady=(0, 10))

        dialog.grab_set()

    def _format_results(self, completed, skipped, errors, cancelled,
                        skipped_files, error_files) -> str:
        if completed > 0 and skipped == 0 and errors == 0 and not cancelled:
            return ("✓ ¡Conversión completada!\n"
                    f"  {completed} archivo(s) convertido(s) exitosamente.\n")

        lines = ["=== Resultados de la conversión ===", ""]
        lines.append(f"✓ Convertidos exitosamente: {completed}")
        lines.append(f"⊘ Omitidos (ya existían):   {skipped}")
        lines.append(f"✗ Con errores:               {errors}")

        if skipped_files:
            lines += ["", "--- Archivos omitidos ---"]
            lines += [f"  • {name}" for name in skipped_files]

        if error_files:
            lines += ["", "--- Archivos con error ---"]
            for name, err in error_files:
                lines.append(f"  • {name}")
                lines.append(f"    Error: {err}")

        if cancelled:
            unprocessed = self._total_files - completed - skipped - errors
            lines += ["", f"--- Cancelados sin procesar: {unprocessed} ---"]

        return "\n".join(lines) + "\n"
