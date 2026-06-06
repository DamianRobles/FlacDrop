import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Callable

from core.scanner import FileNode

# Prefijos de casilla (2 caracteres: símbolo + espacio)
CHECKED = "☑ "      # ☑
UNCHECKED = "☐ "    # ☐
FOLDER_ICON = "\U0001F4C1 "   # 📁
FILE_ICON = "\U0001F3B5 "     # 🎵

EMPTY_MESSAGE = "No se encontraron archivos FLAC en la carpeta Input/"


class CheckboxTreeview(ttk.Treeview):
    """
    ttk.Treeview con soporte de casillas de verificación.
    Las casillas se simulan con prefijos Unicode en el texto de cada item:
      - Deseleccionado: "☐ nombre"
      - Seleccionado:   "☑ nombre"
    Crea sus propias scrollbars dentro de self.frame (el caller empaqueta self.frame).
    """

    def __init__(self, parent, **kwargs):
        # Frame contenedor con scrollbars
        self.frame = ttk.Frame(parent)

        super().__init__(self.frame, columns=("status",), **kwargs)

        # Configuración de columnas
        self.heading("#0", text="Archivo")
        self.heading("status", text="Estado")
        self.column("#0", stretch=True, minwidth=200)
        self.column("status", width=110, stretch=False, anchor="center")

        # Scrollbars
        vsb = ttk.Scrollbar(self.frame, orient="vertical", command=self.yview)
        hsb = ttk.Scrollbar(self.frame, orient="horizontal", command=self.xview)
        self.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.pack(side="left", fill="both", expand=True)

        # Estado interno
        self._check_state: dict[str, bool] = {}
        self._item_paths: dict[str, Path] = {}       # item_id -> Path (solo archivos)
        self._path_to_item: dict[str, str] = {}      # str(Path) -> item_id (solo archivos)
        self._on_check_callback: Callable | None = None
        self._disabled: bool = False
        self._placeholder: str | None = None

        # Toggle al soltar el botón izquierdo
        self.bind("<ButtonRelease-1>", self._on_click)

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def set_on_check_callback(self, callback: Callable | None) -> None:
        self._on_check_callback = callback

    def populate(self, nodes: list[FileNode]) -> None:
        """Limpia el árbol y lo puebla con los nodos dados (selección reiniciada)."""
        self.delete(*self.get_children())
        self._check_state.clear()
        self._item_paths.clear()
        self._path_to_item.clear()
        self._placeholder = None

        if not nodes:
            # Mensaje informativo (sin casilla)
            self._placeholder = self.insert("", "end", text=EMPTY_MESSAGE, values=("",))
            return

        for node in nodes:
            self._insert_node("", node)

    def select_all(self) -> None:
        for item_id in self._check_state:
            self._set_item_checked(item_id, True)
        self._fire_callback()

    def deselect_all(self) -> None:
        for item_id in self._check_state:
            self._set_item_checked(item_id, False)
        self._fire_callback()

    def get_checked_files(self) -> list[Path]:
        """Retorna lista de Path de todos los archivos (no carpetas) marcados."""
        return [path for item_id, path in self._item_paths.items()
                if self._check_state.get(item_id, False)]

    def get_checked_count(self) -> int:
        """Retorna el número de archivos (no carpetas) marcados."""
        return sum(1 for item_id in self._item_paths
                   if self._check_state.get(item_id, False))

    def set_item_status(self, file_path: Path, status: str) -> None:
        """Actualiza la columna 'status' del item correspondiente a file_path."""
        item_id = self._path_to_item.get(str(file_path))
        if item_id:
            self.set(item_id, "status", status)

    def disable_checkboxes(self) -> None:
        self._disabled = True

    def enable_checkboxes(self) -> None:
        self._disabled = False

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #
    def _insert_node(self, parent_id: str, node: FileNode) -> None:
        icon = FOLDER_ICON if node.is_dir else FILE_ICON
        text = UNCHECKED + icon + node.name
        status = "" if node.is_dir else "Pendiente"
        item_id = self.insert(parent_id, "end", text=text, values=(status,), open=True)

        self._check_state[item_id] = False
        if not node.is_dir:
            self._item_paths[item_id] = node.path
            self._path_to_item[str(node.path)] = item_id

        for child in node.children:
            self._insert_node(item_id, child)

    def _on_click(self, event) -> None:
        if self._disabled:
            return
        item_id = self.identify_row(event.y)
        if not item_id or item_id not in self._check_state:
            return
        self._toggle_item(item_id)
        self._fire_callback()

    def _toggle_item(self, item_id: str) -> None:
        new_state = not self._check_state.get(item_id, False)
        self._set_subtree_checked(item_id, new_state)

    def _set_subtree_checked(self, item_id: str, state: bool) -> None:
        self._set_item_checked(item_id, state)
        for child in self.get_children(item_id):
            self._set_subtree_checked(child, state)

    def _set_item_checked(self, item_id: str, state: bool) -> None:
        self._check_state[item_id] = state
        prefix = CHECKED if state else UNCHECKED
        current_text = self.item(item_id, "text")
        # Reemplazar los primeros 2 caracteres (el checkbox anterior)
        base_name = current_text[2:] if len(current_text) >= 2 else current_text
        self.item(item_id, text=prefix + base_name)

    def _fire_callback(self) -> None:
        if self._on_check_callback:
            self._on_check_callback()
