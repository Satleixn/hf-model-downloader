# Hugging Face Model Downloader (GUI)

[English](README.md) | [中文说明](README_CN.md)

A lightweight, zero-bloat desktop GUI tool for downloading **any Hugging Face model repository** with true HTTP Range pause/resume, one-click retry for failed files, and official SHA-256 / Git Blob SHA-1 integrity verification with a live progress bar.

## Features

- **Any Hugging Face Model URL**: Paste a model homepage URL (e.g., `https://huggingface.co/owner/model`), a branch URL (`/tree/<revision>`), a mirror URL (`https://hf-mirror.com/...`), or a plain `owner/model` repo ID.
- **True Pause / Resume / Stop**: Uses chunked HTTP `Range` streaming with `.part` temporary files. Pausing or closing the app preserves downloaded bytes and resumes cleanly from the exact offset.
- **One-Click Retry Failed (`🔄 重试失败`)**: Automatically tracks failed downloads and SHA-mismatched files so you can re-download only the broken or failed files with a single click.
- **One-Click Official SHA Verification (`✔ 校验 SHA`)**:
  - Multi-threaded verification with a dedicated **visual progress bar** (percentage, verified GB, read throughput in MB/s, ETA, and per-file status).
  - Compares **LFS files** against official `lfs.sha256` (SHA-256) and **non-LFS files** against official `blobId` (Git Blob SHA-1).
  - Works both right after download and standalone on any existing local model directory.
- **Mirror & Token Support**: Switch between `https://huggingface.co` and `https://hf-mirror.com`, adjust worker concurrency (1–8 threads), and optionally provide an `HF_TOKEN` for gated repositories.
- **One-Click Windows Launcher**: Double-click `start.bat` in the project root to auto-check dependencies and open the GUI without a lingering console window.

## Quick Start

### Requirements
- Python 3.9+ (with built-in `tkinter`)
- `requests` (`pip install -r requirements.txt`)

### Windows (One-Click)
Double-click **`start.bat`** in the repository root. It automatically checks Python and installs `requests` if needed, then launches the GUI.

### Command Line
```bash
pip install -r requirements.txt
python app.py
```

Optional CLI arguments:
```bash
python app.py --url "https://huggingface.co/owner/model" --dir "H:\Models" --autostart
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
│   └── gui.py          # Tkinter desktop interface
└── tests/              # Unit & local HTTP integration tests
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```

## License

[MIT](LICENSE)
