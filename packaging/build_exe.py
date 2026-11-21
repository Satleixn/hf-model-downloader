"""Reproducible, slim, no-UPX Windows EXE build script for HF Model Downloader."""

import hashlib
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.0.1"
EXE_NAME = f"HF-Model-Downloader-v{VERSION}-win64"
VENV_DIR = ROOT / ".venv-build"
ICON_PATH = ROOT / "assets" / "app.ico"
VERSION_INFO_PATH = ROOT / "packaging" / "version_info.txt"

EXCLUDES = [
    "cryptography",
    "_cffi_backend",
    "OpenSSL",
    "setuptools",
    "pkg_resources",
    "pip",
    "wheel",
    "unittest",
    "pydoc",
    "doctest",
    "pdb",
    "sqlite3",
    "xmlrpc",
    "ftplib",
    "imaplib",
    "poplib",
    "smtplib",
    "telnetlib",
    "turtle",
    "turtledemo",
    "test",
    "tkinter.test",
]


def _make_png(size: int) -> bytes:
    """Generate a minimalist rounded-square blue/gold download icon as RGBA PNG (no Pillow needed)."""
    w = h = size
    rows = []
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    radius = w * 0.44

    for y in range(h):
        row = bytearray([0])  # filter type 0
        ny = (y - cy) / (h / 2.0)
        for x in range(w):
            nx = (x - cx) / (w / 2.0)
            # Rounded square mask
            dx = max(abs(x - cx) - (radius - w * 0.14), 0.0)
            dy = max(abs(y - cy) - (radius - w * 0.14), 0.0)
            in_bg = (dx * dx + dy * dy) <= (w * 0.16) ** 2

            if not in_bg:
                row.extend((0, 0, 0, 0))
                continue

            # Downward arrow + tray in crisp white/gold
            in_shaft = abs(nx) <= 0.13 and -0.42 <= ny <= 0.12
            in_head = 0.02 <= ny <= 0.36 and abs(nx) <= (0.36 - ny) * 1.15
            in_tray = (0.44 <= ny <= 0.56 and abs(nx) <= 0.44)

            if in_shaft or in_head:
                row.extend((255, 210, 30, 255))  # HF warm gold
            elif in_tray:
                row.extend((255, 255, 255, 255))  # crisp white tray
            else:
                # Deep slate-blue gradient
                t = (ny + 1.0) / 2.0
                r = int(24 + 14 * (1 - t))
                g = int(58 + 38 * (1 - t))
                b = int(120 + 55 * (1 - t))
                row.extend((r, g, b, 255))
        rows.append(bytes(row))

    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def ensure_icon(icon_path: Path) -> None:
    """Create multi-size PNG-backed Windows .ico file if missing."""
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 48, 256]
    pngs = [_make_png(s) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = []
    for s, data in zip(sizes, pngs):
        dim = 0 if s >= 256 else s
        entries.append(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    icon_path.write_bytes(header + b"".join(entries) + b"".join(pngs))


def generate_spec(spec_path: Path) -> None:
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    [r"{str(ROOT / 'app.py')}"],
    pathex=[r"{str(ROOT)}"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={EXCLUDES!r},
    noarchive=False,
    optimize=1,
)

# Trim unused Tcl/Tk timezone data, demos, and non-essential locale catalogs
def _keep_data(entry):
    dest = entry[0].replace("\\\\", "/").lower()
    if "_tcl_data/tzdata/" in dest or "_tcl_data/msgs/" in dest or "_tk_data/demos/" in dest or "_tk_data/msgs/" in dest:
        return False
    return True

a.datas = [d for d in a.datas if _keep_data(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name={EXE_NAME!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r"{str(ICON_PATH)}",
    version=r"{str(VERSION_INFO_PATH)}",
)
"""
    spec_path.write_text(spec_content, encoding="utf-8")


def main() -> None:
    ensure_icon(ICON_PATH)
    print(f"[1/3] Icon ready: {ICON_PATH}")

    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    spec_path = ROOT / f"{EXE_NAME}.spec"
    generate_spec(spec_path)

    print(f"[2/3] Building {EXE_NAME}.exe (no UPX, excluded unused modules, trimmed Tcl/Tk) ...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(spec_path)],
        cwd=str(ROOT),
        check=True,
    )

    exe_path = ROOT / "dist" / f"{EXE_NAME}.exe"
    if not exe_path.is_file():
        raise FileNotFoundError(f"Expected EXE not found: {exe_path}")

    sha256 = hashlib.sha256(exe_path.read_bytes()).hexdigest().upper()
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[3/3] Build succeeded!")
    print(f"      Path   : {exe_path}")
    print(f"      Size   : {size_mb:.2f} MB")
    print(f"      SHA-256: {sha256}")


if __name__ == "__main__":
    main()
