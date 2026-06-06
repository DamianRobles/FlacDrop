@echo off
setlocal
echo ============================================
echo   FLAC to MP3 Converter - Configuracion
echo ============================================
echo.

set "PYTHON_CMD="
python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if "%PYTHON_CMD%"=="" (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if "%PYTHON_CMD%"=="" (
    echo ERROR: Python no encontrado.
    echo Instala Python 3.8+ desde https://www.python.org
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creando entorno virtual...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 ( echo ERROR al crear venv. & pause & exit /b 1 )
)

echo Instalando dependencias...
call .venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

echo Descargando FFmpeg...
python download_ffmpeg.py --platform windows
if errorlevel 1 ( echo ERROR: Fallo al descargar FFmpeg. & pause & exit /b 1 )

echo.
echo Configuracion completada.
echo Ejecuta run.bat para iniciar el programa.
pause
