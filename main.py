import sys
import tkinter as tk
from tkinter import messagebox

from core.ffmpeg_manager import check_ffmpeg_exists
from gui.app import App


def main():
    if not check_ffmpeg_exists():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "FFmpeg no encontrado",
            "Los binarios de FFmpeg no se encontraron en la carpeta bin/.\n\n"
            "Ejecuta setup.bat (Windows) o ./setup.sh (Linux) para configurar el programa.",
        )
        root.destroy()
        sys.exit(1)

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
