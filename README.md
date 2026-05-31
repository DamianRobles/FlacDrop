<div align="center">

# 🎵 FlacDrop

**Local FLAC to MP3 converter at 320kbps with a simple GUI.**

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey?style=flat-square)
![FFmpeg](https://img.shields.io/badge/FFmpeg-bundled-007808?style=flat-square&logo=ffmpeg&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

</div>

---

FlacDrop converts your FLAC music library to MP3 at 320 kbps — locally, with no internet required and no accounts. Drop your files into the `Input/` folder, pick what to convert, and get your MP3s in `Output/`. FFmpeg is bundled, so there's nothing extra to install.

## ✨ Features

- 🎛️ **320 kbps MP3** output via the LAME encoder
- 🏷️ **Preserves metadata** — title, artist, album, track number, year, and more
- 🖼️ **Preserves cover art** embedded in the original FLAC
- 📁 **Mirrors folder structure** — `Input/Artist/Album/song.flac` → `Output/Artist/Album/song.mp3`
- ☑️ **Selective conversion** — choose individual songs or entire folders
- 📊 **Real-time progress** — two progress bars (current file + overall) with estimated time remaining
- ⛔ **Cancellable** — stop the conversion at any moment; no partial files left behind
- ⚠️ **Non-destructive** — existing MP3s in `Output/` are never overwritten
- 📦 **Portable** — FFmpeg binaries included; just clone and run
- 🖥️ **Cross-platform** — Windows 10/11 and Linux x86_64

---

## 🛠️ Built with

| Tool | Role |
|---|---|
| [Python 3.8+](https://www.python.org/) | Core language |
| [Tkinter](https://docs.python.org/3/library/tkinter.html) | GUI framework (built into Python) |
| [FFmpeg](https://ffmpeg.org/) | Audio conversion and metadata handling |
| `threading` + `queue` | Non-blocking UI during conversion |
| `pathlib` | Cross-platform file and path management |
| `subprocess` | FFmpeg process management |

No external Python packages required.

---

## ⚙️ Requirements

- Python **3.8 or higher** — [Download here](https://www.python.org/downloads/)
- Internet connection — only during the **first-time setup** to download FFmpeg
- Windows 10/11 or Linux x86_64

---

## 🚀 Setup

Run the setup script once. It creates a virtual environment and downloads the FFmpeg binaries automatically.

**Windows:**
```
setup.bat
```

**Linux:**
```bash
chmod +x setup.sh run.sh
./setup.sh
```

---

## ▶️ Usage

**1. Launch the app**

```
run.bat          # Windows
./run.sh         # Linux
```

**2. Add your music**

Copy your FLAC files (or folders containing them) into the `Input/` folder.

```
Input/
├── Daft Punk/
│   └── Random Access Memories/
│       ├── 01 - Get Lucky.flac
│       └── 02 - Instant Crush.flac
└── some_single.flac
```

**3. Select and convert**

- Click **"Actualizar lista"** to scan the `Input/` folder
- Check the files or folders you want to convert
- Click **"Convertir seleccionados"**

**4. Get your MP3s**

Converted files appear in `Output/`, preserving the same folder structure:

```
Output/
├── Daft Punk/
│   └── Random Access Memories/
│       ├── 01 - Get Lucky.mp3
│       └── 02 - Instant Crush.mp3
└── some_single.mp3
```

---

## 📂 Project structure

```
FlacDrop/
├── Input/               ← Place your FLAC files here
├── Output/              ← Converted MP3s appear here
├── bin/
│   ├── windows/         ← ffmpeg.exe, ffprobe.exe (downloaded by setup)
│   └── linux/           ← ffmpeg, ffprobe (downloaded by setup)
├── core/
│   ├── ffmpeg_manager.py
│   ├── scanner.py
│   └── converter.py
├── gui/
│   ├── app.py
│   └── file_tree.py
├── main.py
├── download_ffmpeg.py
├── setup.bat / setup.sh
└── run.bat / run.sh
```

---

## 📋 Notes

- Files that already exist in `Output/` are **skipped**, never overwritten. A summary of skipped files is shown at the end.
- If a file fails to convert (e.g. corrupted FLAC), FlacDrop logs the error and **continues** with the rest.
- Cancelling mid-conversion cleans up any partial MP3 files automatically.
- The app runs entirely offline after setup. No telemetry, no cloud.

---

## 📄 License

FlacDrop is licensed under the [MIT License](LICENSE).  
This project bundles [FFmpeg](https://ffmpeg.org/legal.html), which is licensed under the LGPL 2.1+.
