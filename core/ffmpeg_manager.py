import sys
from pathlib import Path


def get_base_dir() -> Path:
    return Path(__file__).parent.parent.resolve()


def get_ffmpeg_path() -> Path:
    base = get_base_dir()
    if sys.platform == "win32":
        return base / "bin" / "windows" / "ffmpeg.exe"
    return base / "bin" / "linux" / "ffmpeg"


def get_ffprobe_path() -> Path:
    base = get_base_dir()
    if sys.platform == "win32":
        return base / "bin" / "windows" / "ffprobe.exe"
    return base / "bin" / "linux" / "ffprobe"


def check_ffmpeg_exists() -> bool:
    return get_ffmpeg_path().exists() and get_ffprobe_path().exists()


def get_input_dir() -> Path:
    return get_base_dir() / "Input"


def get_output_dir() -> Path:
    return get_base_dir() / "Output"
