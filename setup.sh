#!/bin/bash
set -e
echo "============================================"
echo "  FLAC to MP3 Converter - Configuracion"
echo "============================================"
echo ""

if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python3 no encontrado. Instala Python 3.8+"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
fi

echo "Instalando dependencias..."
source .venv/bin/activate
pip install -r requirements.txt --quiet

echo "Descargando FFmpeg..."
python download_ffmpeg.py --platform linux

chmod +x bin/linux/ffmpeg bin/linux/ffprobe 2>/dev/null || true

echo ""
echo "Configuracion completada."
echo "Ejecuta ./run.sh para iniciar el programa."
