import queue
import subprocess
import threading
import time
from pathlib import Path


class Converter:
    def __init__(self, ffmpeg: Path, ffprobe: Path,
                 cancel_event: threading.Event, progress_queue: queue.Queue):
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.cancel_event = cancel_event
        self.progress_queue = progress_queue

    def convert_all(self, file_pairs: list[tuple[Path, Path]]) -> None:
        """Punto de entrada del worker thread."""
        results = {"completed": 0, "skipped": 0, "errors": 0,
                   "skipped_files": [], "error_files": [], "cancelled": False}
        times = []  # tiempos de conversión de archivos completados
        total = len(file_pairs)

        for idx, (inp, out) in enumerate(file_pairs, start=1):
            if self.cancel_event.is_set():
                results["cancelled"] = True
                break

            t0 = time.time()
            status, error_msg = self._convert_single(inp, out, idx, total, times)
            elapsed = time.time() - t0

            if status == "ok":
                results["completed"] += 1
                times.append(elapsed)
            elif status == "skipped":
                results["skipped"] += 1
                results["skipped_files"].append(inp.name)
            elif status == "error":
                results["errors"] += 1
                results["error_files"].append((inp.name, error_msg or "Error desconocido"))
            elif status == "cancelled":
                results["cancelled"] = True
                break

            self.progress_queue.put({
                "type": "file_done",
                "file": inp.name,
                "status": status,
                "error_msg": error_msg,
                "file_index": idx,
                "total_files": total,
            })

        self.progress_queue.put({"type": "done", **results})

    def _get_duration(self, path: Path) -> float:
        """Obtiene la duración del archivo en segundos. Retorna 0.0 si falla."""
        try:
            result = subprocess.run(
                [str(self.ffprobe), "-v", "error",
                 "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=30
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _convert_single(self, inp: Path, out: Path,
                        idx: int, total: int, times: list) -> tuple[str, str | None]:
        """Convierte un archivo. Retorna (status, error_msg)."""
        # 1. Comprobar si ya existe
        if out.exists():
            return "skipped", None

        # 2. Crear directorio destino
        out.parent.mkdir(parents=True, exist_ok=True)

        # 3. Obtener duración para calcular progreso
        duration = self._get_duration(inp)

        # 4. Construir comando ffmpeg
        cmd = [
            str(self.ffmpeg), "-y", "-i", str(inp),
            "-map", "0:a", "-map", "0:v?",
            "-c:a", "libmp3lame", "-b:a", "320k",
            "-c:v", "copy",
            "-map_metadata", "0", "-id3v2_version", "3",
            "-progress", "pipe:1", "-nostats",
            str(out)
        ]

        # 5. Lanzar proceso
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace"
            )
        except Exception as e:
            return "error", str(e)

        # 6. Leer progreso
        for line in process.stdout:
            if self.cancel_event.is_set():
                process.terminate()
                process.wait()
                if out.exists():
                    out.unlink()
                return "cancelled", None

            line = line.strip()
            if line.startswith("out_time_us=") and duration > 0:
                try:
                    out_time_s = int(line.split("=", 1)[1]) / 1_000_000
                    pct = min(out_time_s / duration * 100.0, 100.0)
                    eta = self._calculate_eta(times, total - idx)
                    self.progress_queue.put({
                        "type": "progress",
                        "current_file": inp.name,
                        "file_index": idx,
                        "total_files": total,
                        "file_percent": pct,
                        "eta_seconds": eta,
                    })
                except (ValueError, ZeroDivisionError):
                    pass

        process.wait()

        if process.returncode != 0 and not self.cancel_event.is_set():
            stderr_output = process.stderr.read() if process.stderr else ""
            if out.exists():
                out.unlink()
            return "error", f"ffmpeg exit code {process.returncode}"

        return "ok", None

    def _calculate_eta(self, times: list, remaining: int) -> float | None:
        if not times:
            return None
        avg = sum(times) / len(times)
        return avg * remaining
