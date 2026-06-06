import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple


class Converter:
    def __init__(
        self,
        ffmpeg: Path,
        ffprobe: Path,
        cancel_event: threading.Event,
        progress_queue: queue.Queue,
    ):
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.cancel_event = cancel_event
        self.progress_queue = progress_queue

    def convert_all(self, file_pairs: List[Tuple[Path, Path]]) -> None:
        """Punto de entrada del worker thread."""
        results = {
            "completed": 0,
            "skipped": 0,
            "errors": 0,
            "skipped_files": [],
            "error_files": [],
            "cancelled": False,
        }
        times = []
        total = len(file_pairs)

        for idx, (inp, out) in enumerate(file_pairs, start=1):
            if self.cancel_event.is_set():
                results["cancelled"] = True
                break

            start_time = time.time()
            status, error_msg = self._convert_single(inp, out, idx, total, times)
            elapsed = time.time() - start_time

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

            self.progress_queue.put(
                {
                    "type": "file_done",
                    "file": inp.name,
                    "status": status,
                    "error_msg": error_msg,
                    "file_index": idx,
                    "total_files": total,
                }
            )

        self.progress_queue.put({"type": "done", **results})

    def _get_duration(self, path: Path) -> float:
        """Obtiene la duracion del archivo en segundos. Retorna 0.0 si falla."""
        try:
            result = subprocess.run(
                [
                    str(self.ffprobe),
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _convert_single(
        self,
        inp: Path,
        out: Path,
        idx: int,
        total: int,
        times: List[float],
    ) -> Tuple[str, Optional[str]]:
        """Convierte un archivo. Retorna (status, error_msg)."""
        if out.exists():
            return "skipped", None

        out.parent.mkdir(parents=True, exist_ok=True)
        duration = self._get_duration(inp)

        cmd = [
            str(self.ffmpeg),
            "-y",
            "-i",
            str(inp),
            "-map",
            "0:a",
            "-map",
            "0:v?",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "320k",
            "-c:v",
            "copy",
            "-map_metadata",
            "0",
            "-id3v2_version",
            "3",
            "-progress",
            "pipe:1",
            "-nostats",
            str(out),
        ]

        self.progress_queue.put(
            {
                "type": "progress",
                "current_file": inp.name,
                "file_index": idx,
                "total_files": total,
                "file_percent": 0.0,
                "eta_seconds": self._calculate_eta(times, total - idx),
            }
        )

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            return "error", str(exc)

        stderr_lines = []
        stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(process, stderr_lines),
            daemon=True,
        )
        stderr_thread.start()

        try:
            if process.stdout is not None:
                for line in process.stdout:
                    if self.cancel_event.is_set():
                        self._terminate_process(process)
                        self._delete_partial_output(out)
                        return "cancelled", None

                    line = line.strip()
                    if line.startswith("out_time_us=") and duration > 0:
                        try:
                            out_time_s = int(line.split("=", 1)[1]) / 1_000_000
                            pct = min(out_time_s / duration * 100.0, 100.0)
                        except (ValueError, ZeroDivisionError):
                            continue

                        self.progress_queue.put(
                            {
                                "type": "progress",
                                "current_file": inp.name,
                                "file_index": idx,
                                "total_files": total,
                                "file_percent": pct,
                                "eta_seconds": self._calculate_eta(times, total - idx),
                            }
                        )
                    elif line == "progress=end":
                        break

            return_code = process.wait()
            stderr_thread.join(timeout=1)
        except Exception as exc:
            self._terminate_process(process)
            self._delete_partial_output(out)
            return "error", str(exc)

        if self.cancel_event.is_set():
            self._delete_partial_output(out)
            return "cancelled", None

        if return_code != 0:
            self._delete_partial_output(out)
            return "error", self._format_error(return_code, stderr_lines)

        self.progress_queue.put(
            {
                "type": "progress",
                "current_file": inp.name,
                "file_index": idx,
                "total_files": total,
                "file_percent": 100.0,
                "eta_seconds": self._calculate_eta(times, total - idx),
            }
        )
        return "ok", None

    def _calculate_eta(self, times: List[float], remaining: int) -> Optional[float]:
        if not times:
            return None
        avg = sum(times) / len(times)
        return avg * remaining

    def _drain_stderr(self, process: subprocess.Popen, stderr_lines: List[str]) -> None:
        if process.stderr is None:
            return
        for line in process.stderr:
            line = line.strip()
            if line:
                stderr_lines.append(line)

    def _terminate_process(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _delete_partial_output(self, output_path: Path) -> None:
        if output_path.exists():
            output_path.unlink()

    def _format_error(self, return_code: int, stderr_lines: List[str]) -> str:
        for line in reversed(stderr_lines):
            if line:
                return f"ffmpeg exit code {return_code}: {line[:200]}"
        return f"ffmpeg exit code {return_code}"
