#!/usr/bin/env python3
"""
Descarga los binarios de FFmpeg bundleados para el proyecto.
Uso: python download_ffmpeg.py --platform [windows|linux]
"""
import argparse
import os
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

FFMPEG_URLS = {
    "windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl.zip",
    "linux": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
}

BINARIES = {
    "windows": ["ffmpeg.exe", "ffprobe.exe"],
    "linux": ["ffmpeg", "ffprobe"],
}


def binaries_exist(platform: str) -> bool:
    """True si todos los binarios de la plataforma ya existen."""
    bin_dir = BASE_DIR / "bin" / platform
    return all((bin_dir / binary).exists() for binary in BINARIES[platform])


def progress_hook(count, block_size, total_size):
    """Muestra el progreso de descarga en consola."""
    if total_size > 0:
        pct = min(count * block_size / total_size * 100, 100)
        print(f"\r  Descargando... {pct:.1f}%", end="", flush=True)


def download_windows():
    """Descarga y extrae ffmpeg.exe y ffprobe.exe para Windows."""
    bin_dir = BASE_DIR / "bin" / "windows"
    bin_dir.mkdir(parents=True, exist_ok=True)
    tmp_zip = BASE_DIR / "bin" / "ffmpeg_tmp.zip"

    try:
        urllib.request.urlretrieve(FFMPEG_URLS["windows"], tmp_zip, progress_hook)
        print()

        with zipfile.ZipFile(tmp_zip, "r") as zip_file:
            for member in zip_file.namelist():
                filename = Path(member).name
                if filename in BINARIES["windows"]:
                    dest = bin_dir / filename
                    dest.write_bytes(zip_file.read(member))
                    print(f"  Extraido: {dest}")
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink()


def download_linux():
    """Descarga y extrae ffmpeg y ffprobe para Linux."""
    bin_dir = BASE_DIR / "bin" / "linux"
    bin_dir.mkdir(parents=True, exist_ok=True)
    tmp_tar = BASE_DIR / "bin" / "ffmpeg_tmp.tar.xz"

    try:
        urllib.request.urlretrieve(FFMPEG_URLS["linux"], tmp_tar, progress_hook)
        print()

        with tarfile.open(tmp_tar, "r:xz") as tar_file:
            for member in tar_file.getmembers():
                filename = Path(member.name).name
                if filename in BINARIES["linux"] and member.isfile():
                    source = tar_file.extractfile(member)
                    if source is None:
                        continue

                    dest = bin_dir / filename
                    dest.write_bytes(source.read())
                    os.chmod(dest, 0o755)
                    print(f"  Extraido: {dest}")
    finally:
        if tmp_tar.exists():
            tmp_tar.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["windows", "linux"], required=True)
    args = parser.parse_args()

    if binaries_exist(args.platform):
        print("FFmpeg ya esta instalado. Nada que hacer.")
        return

    print(f"Descargando FFmpeg para {args.platform}...")
    try:
        if args.platform == "windows":
            download_windows()
        else:
            download_linux()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not binaries_exist(args.platform):
        print(
            "ERROR: Los binarios no se encontraron en el archivo descargado.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("FFmpeg descargado correctamente.")


if __name__ == "__main__":
    main()
