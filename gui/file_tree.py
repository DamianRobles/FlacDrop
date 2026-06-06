from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.scanner import FileNode


class CheckboxTreeview(ttk.Treeview):
    """
    ttk.Treeview con soporte de casillas de verificacion simuladas en el texto.
    """

    CHECKED_PREFIX = "☑ "
    UNCHECKED_PREFIX = "☐ "
    FOLDER_ICON = "📁 "
    FILE_ICON = "🎵 "

    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("columns", ("status",))
        super().__init__(master, **kwargs)

        self.heading("#0", text="Archivo")
        self.heading("status", text="Estado")
        self.column("#0", minwidth=260, stretch=True)
        self.column("status", width=110, minwidth=90, anchor="center", stretch=False)

        self._check_state: Dict[str, bool] = {}
        self._item_paths: Dict[str, Path] = {}
        self._path_items: Dict[Path, str] = {}
        self._on_check_callback: Optional[Callable[[], None]] = None
        self._disabled = False

        self.bind("<ButtonRelease-1>", self._on_click, add="+")

    def set_on_check_callback(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_check_callback = callback

    def populate(self, nodes: List["FileNode"]) -> None:
        """Limpia el arbol y lo puebla con los nodos dados."""
        self.delete(*self.get_children())
        self._check_state.clear()
        self._item_paths.clear()
        self._path_items.clear()

        for node in nodes:
            self._insert_node("", node)

    def select_all(self) -> None:
        """Marca todas las casillas."""
        for item_id in self.get_children(""):
            self._set_subtree_checked(item_id, True)
        self._notify_check_changed()

    def deselect_all(self) -> None:
        """Desmarca todas las casillas."""
        for item_id in self.get_children(""):
            self._set_subtree_checked(item_id, False)
        self._notify_check_changed()

    def get_checked_files(self) -> List[Path]:
        """Retorna lista de Path de todos los archivos marcados."""
        checked_files = []
        for item_id, path in self._item_paths.items():
            if self._check_state.get(item_id, False):
                checked_files.append(path)
        return checked_files

    def get_checked_count(self) -> int:
        """Retorna el numero de archivos marcados."""
        return len(self.get_checked_files())

    def set_item_status(self, file_path: Path, status: str) -> None:
        """Actualiza la columna 'status' del item correspondiente a file_path."""
        item_id = self._path_items.get(Path(file_path))
        if item_id is not None:
            self.set(item_id, "status", status)

    def disable_checkboxes(self) -> None:
        """Deshabilita la interaccion con las casillas."""
        self._disabled = True

    def enable_checkboxes(self) -> None:
        """Rehabilita la interaccion con las casillas."""
        self._disabled = False

    def _insert_node(self, parent: str, node: "FileNode") -> str:
        icon = self.FOLDER_ICON if node.is_dir else self.FILE_ICON
        status = "" if node.is_dir else "—"
        item_id = self.insert(
            parent,
            "end",
            text=self.UNCHECKED_PREFIX + icon + node.name,
            values=(status,),
            open=True,
        )
        self._check_state[item_id] = False

        if node.is_dir:
            for child in node.children:
                self._insert_node(item_id, child)
        else:
            path = Path(node.path)
            self._item_paths[item_id] = path
            self._path_items[path] = item_id

        return item_id

    def _on_click(self, event) -> None:
        if self._disabled:
            return

        item_id = self.identify_row(event.y)
        if not item_id:
            return

        self._toggle_item(item_id)
        self._notify_check_changed()

    def _toggle_item(self, item_id: str) -> None:
        new_state = not self._check_state.get(item_id, False)

        if self.get_children(item_id):
            self._set_subtree_checked(item_id, new_state)
        else:
            self._set_item_checked(item_id, new_state)

        self._update_ancestors(item_id)

    def _set_subtree_checked(self, item_id: str, state: bool) -> None:
        self._set_item_checked(item_id, state)
        for child in self.get_children(item_id):
            self._set_subtree_checked(child, state)

    def _set_item_checked(self, item_id: str, state: bool) -> None:
        self._check_state[item_id] = state
        current_text = self.item(item_id, "text")
        base_text = self._strip_checkbox_prefix(current_text)
        prefix = self.CHECKED_PREFIX if state else self.UNCHECKED_PREFIX
        self.item(item_id, text=prefix + base_text)

    def _update_ancestors(self, item_id: str) -> None:
        parent = self.parent(item_id)
        while parent:
            children = self.get_children(parent)
            all_checked = bool(children) and all(
                self._check_state.get(child, False) for child in children
            )
            self._set_item_checked(parent, all_checked)
            parent = self.parent(parent)

    def _strip_checkbox_prefix(self, text: str) -> str:
        if text.startswith(self.CHECKED_PREFIX):
            return text[len(self.CHECKED_PREFIX) :]
        if text.startswith(self.UNCHECKED_PREFIX):
            return text[len(self.UNCHECKED_PREFIX) :]
        return text

    def _notify_check_changed(self) -> None:
        if self._on_check_callback is not None:
            self._on_check_callback()
