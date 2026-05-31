from dataclasses import dataclass, field
from pathlib import Path

FLAC_EXTENSIONS = {".flac"}


@dataclass
class FileNode:
    name: str
    path: Path
    is_dir: bool
    children: list["FileNode"] = field(default_factory=list)


def scan_input(input_dir: Path) -> list[FileNode]:
    """
    Escanea input_dir recursivamente.
    Retorna lista de FileNode ordenada (carpetas primero, luego archivos, ambos alfabéticos).
    Solo incluye directorios que contengan al menos un FLAC en cualquier nivel descendiente.
    """
    return _scan_directory(input_dir)


def _scan_directory(directory: Path) -> list[FileNode]:
    nodes = []
    try:
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except (PermissionError, FileNotFoundError):
        return nodes

    for entry in entries:
        if entry.is_dir():
            children = _scan_directory(entry)
            if children:  # solo incluir si tiene FLAC dentro
                nodes.append(FileNode(name=entry.name, path=entry, is_dir=True, children=children))
        elif entry.is_file() and entry.suffix.lower() in FLAC_EXTENSIONS:
            nodes.append(FileNode(name=entry.name, path=entry, is_dir=False))

    return nodes


def count_flac_files(nodes: list[FileNode]) -> int:
    """Cuenta el total de archivos FLAC en el árbol."""
    count = 0
    for node in nodes:
        if node.is_dir:
            count += count_flac_files(node.children)
        else:
            count += 1
    return count
