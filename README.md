# Hugging Face Model Downloader (GUI)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Cross--Platform-lightgrey.svg)](#quick-start)

[English](README.md) | [中文说明](README_CN.md)

A lightweight, zero-bloat desktop GUI tool for downloading **any Hugging Face model repository** with true HTTP Range pause/resume, one-click retry for failed files, official SHA-256 / Git Blob SHA-1 integrity verification with a live progress bar, and instant Chinese/English UI switching.

## Features

- **Any Hugging Face Model URL**: Paste a model homepage URL (e.g., `https://huggingface.co/owner/model`), a branch URL (`/tree/<revision>`), a mirror URL (`https://hf-mirror.com/...`), or a plain `owner/model` repo ID.
- **Live Bilingual UI (`中文` / `English`)**: Built-in top-right language switcher dropdown (defaults to Chinese; switches the entire interface live without restarting).
- **Smart Save Directory**: Defaults to your OS system **Downloads** folder on first launch (via Windows `SHGetKnownFolderPath`). Remembers the folder chosen via **Browse...**, and automatically resets to your system Downloads folder with a clear alert if a previously saved directory disappears.
- **True Pause / Resume / Stop**: Uses chunked HTTP `Range` streaming with `.part` temporary files. Pausing or closing the app preserves downloaded bytes and resumes cleanly from the exact offset.
- **One-Click Retry Failed (`Retry Failed`)**: Automatically tracks failed downloads and SHA-mismatched files so you can re-download only the broken or failed files with a single click.
- **One-Click Official SHA Verification (`Verify SHA`)**:
  - Multi-threaded verification with a dedicated **visual progress bar** (percentage, verified GB, read throughput in MB/s, ETA, and per-file status).
  - Compares **LFS files** against official `lfs.sha256` (SHA-256) and **non-LFS files** against official `blobId` (Git Blob SHA-1).
  - Works both right after download and standalone on any existing local model directory.
- **Mirror & Token Support**: Switch between `https://huggingface.co` and `https://hf-mirror.com`, adjust worker concurrency (1–8 threads), and optionally provide an `HF_TOKEN` for gated repositories.

## Quick Start

### Option 1: Standalone Windows Builds (No Python Required)
Go to the [Releases](https://github.com/Satleixn/hf-model-downloader/releases) page (`v1.0.2`):
- **Portable ZIP (Recommended)**: Download **`HF-Model-Downloader-v1.0.2-win64-portable.zip`**, extract, and run `HF-Model-Downloader.exe`. Runs directly without extracting temporary directories (faster startup and immune to `Could not create temporary directory!` errors).
- **Single-File EXE**: Download **`HF-Model-Downloader-v1.0.2-win64.exe`** and double-click to launch.

Both builds are compiled **without UPX** (`upx=False`), include Windows PE version metadata, a custom icon, and published SHA-256 checksums. You can also rebuild them locally via `python packaging/build_exe.py`.

### Option 2: Run from Source (Zero SmartScreen Prompt)
- Requirements: Python 3.9+ (with built-in `tkinter`) and `requests` (`pip install -r requirements.txt`)
- Windows one-click: Clone the repo (`git clone https://github.com/Satleixn/hf-model-downloader.git`) and double-click **`start.bat`** in the project root.
- Command line:
```bash
pip install -r requirements.txt
python app.py
```

Optional CLI arguments:
```bash
python app.py --url "https://huggingface.co/owner/model" --dir "D:\Models" --lang en --autostart
```

## Windows SmartScreen & Antivirus FAQ

- **Why does Windows SmartScreen appear on a downloaded `.exe`?**
  Windows marks files downloaded from the internet with a Mark-of-the-Web flag and warns on any open-source executable that is not signed with a paid CA Authenticode certificate.
- **How to run cleanly**:
  1. Click **More info → Run anyway** (or right-click the downloaded `.zip`/`.exe` → **Properties** → check **Unblock** before running/extracting).
  2. Or run from source via `git clone` + `start.bat` (files cloned by Git never trigger SmartScreen).
- **Seeing `Could not create temporary directory!` on the single-file `.exe`?**
  Use **`HF-Model-Downloader-v1.0.2-win64-portable.zip`** instead—it does not extract to `%TEMP%` at runtime.

## Project Structure

```text
hf-model-downloader/
├── start.bat           # Windows one-click quick launcher (source mode)
├── app.py              # CLI & GUI entry point
├── requirements.txt    # Runtime dependencies
├── assets/
│   └── app.ico         # Custom application icon
├── packaging/
│   ├── build_exe.py    # Reproducible no-UPX build script (onefile + portable ZIP)
│   └── version_info.txt# Windows PE version metadata
├── src/
│   ├── config.py       # OS default Downloads resolution & path persistence
│   ├── hf_parser.py    # Hugging Face URL/ID parser & API metadata client
│   ├── downloader.py   # Multi-threaded resumable download engine + retry failed
│   ├── verifier.py     # Multi-threaded official SHA-256 / SHA-1 verifier
│   ├── i18n.py         # Chinese / English live UI translations
│   └── gui.py          # Tkinter desktop interface
└── tests/              # Unit & local HTTP integration tests
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for full details.

## Disclaimer

- This project is an independent open-source utility and is **not affiliated with, endorsed by, or officially connected to Hugging Face, Inc.**
- Users are solely responsible for complying with the license terms, usage policies, access restrictions (including gated model agreements), and applicable local laws and regulations for any model or file downloaded with this tool.
- This software is provided **"AS IS"**, without warranty of any kind, express or implied. The authors and contributors assume no liability for any data loss, network/storage costs, or misuse arising from the use of this software.
