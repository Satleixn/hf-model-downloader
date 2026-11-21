# Hugging Face Model Downloader (GUI)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Cross--Platform-lightgrey.svg)](#quick-start)

[English](README.md) | [中文说明](README_CN.md)

A lightweight, zero-bloat desktop GUI tool for downloading **any Hugging Face model repository** with true HTTP Range pause/resume, one-click retry for failed files, official SHA-256 / Git Blob SHA-1 integrity verification with a live progress bar, and instant Chinese/English UI switching.

## Features

- **Any Hugging Face Model URL**: Paste a model homepage URL (e.g., `https://huggingface.co/owner/model`), a branch URL (`/tree/<revision>`), a mirror URL (`https://hf-mirror.com/...`), or a plain `owner/model` repo ID.
- **Live Bilingual UI (`中文` / `English`)**: Built-in top-right language switcher dropdown (defaults to Chinese; switches the entire interface live without restarting).
- **True Pause / Resume / Stop**: Uses chunked HTTP `Range` streaming with `.part` temporary files. Pausing or closing the app preserves downloaded bytes and resumes cleanly from the exact offset.
- **One-Click Retry Failed (`Retry Failed`)**: Automatically tracks failed downloads and SHA-mismatched files so you can re-download only the broken or failed files with a single click.
- **One-Click Official SHA Verification (`Verify SHA`)**:
  - Multi-threaded verification with a dedicated **visual progress bar** (percentage, verified GB, read throughput in MB/s, ETA, and per-file status).
  - Compares **LFS files** against official `lfs.sha256` (SHA-256) and **non-LFS files** against official `blobId` (Git Blob SHA-1).
  - Works both right after download and standalone on any existing local model directory.
- **Mirror & Token Support**: Switch between `https://huggingface.co` and `https://hf-mirror.com`, adjust worker concurrency (1–8 threads), and optionally provide an `HF_TOKEN` for gated repositories.
- **One-Click Windows Launcher**: Double-click `start.bat` in the project root to auto-check dependencies and open the GUI without a lingering console window.

## Quick Start

### Option 1: Standalone Windows EXE (No Python Required)
Download **`HF-Model-Downloader-v1.0.1-win64.exe`** from the [Releases](https://github.com/Satleixn/hf-model-downloader/releases) page and double-click to launch.

- Default save directory: `C:\Users\<User>\Downloads`
- Your chosen folder via **Browse...** is remembered automatically; if a remembered folder no longer exists, the app will prompt you to select a new one.
- Built in a clean isolated environment **without UPX** (to minimize antivirus false positives), with Windows PE version metadata and SHA-256 checksums published on every release. You can also build it yourself with `python packaging/build_exe.py`.

### Option 2: Run from Source
- Requirements: Python 3.9+ (with built-in `tkinter`) and `requests` (`pip install -r requirements.txt`)
- Windows one-click: Double-click **`start.bat`** in the repository root.
- Command line:
```bash
pip install -r requirements.txt
python app.py
```

Optional CLI arguments:
```bash
python app.py --url "https://huggingface.co/owner/model" --dir "H:\Models" --lang en --autostart
```

## Project Structure

```text
hf-model-downloader/
├── start.bat           # Windows one-click quick launcher
├── app.py              # CLI & GUI entry point
├── requirements.txt    # Runtime dependencies
├── src/
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
