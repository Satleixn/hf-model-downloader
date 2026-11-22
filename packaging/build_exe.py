"""Reproducible, slim, no-UPX Windows build script (onefile EXE + onedir portable ZIP)."""

import hashlib
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.1.0"
EXE_NAME = f"HF-Model-Downloader-v{VERSION}-win64"
PORTABLE_DIR_NAME = f"HF-Model-Downloader-v{VERSION}-win64-portable"
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
    """Generate a minimalist rounded-square blue/gold download icon as RGBA PNG."""
    w = h = size
    rows = []
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    radius = w * 0.44

    for y in range(h):
        row = bytearray([0])
        ny = (y - cy) / (h / 2.0)
        for x in range(w):
            nx = (x - cx) / (w / 2.0)
            dx = max(abs(x - cx) - (radius - w * 0.14), 0.0)
            dy = max(abs(y - cy) - (radius - w * 0.14), 0.0)
            in_bg = (dx * dx + dy * dy) <= (w * 0.16) ** 2

            if not in_bg:
                row.extend((0, 0, 0, 0))
                continue

            in_shaft = abs(nx) <= 0.13 and -0.42 <= ny <= 0.12
            in_head = 0.02 <= ny <= 0.36 and abs(nx) <= (0.36 - ny) * 1.15
            in_tray = 0.44 <= ny <= 0.56 and abs(nx) <= 0.44

            if in_shaft or in_head:
                row.extend((255, 210, 30, 255))
            elif in_tray:
                row.extend((255, 255, 255, 255))
            else:
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


def _common_analysis_block() -> str:
    return f"""# -*- mode: python ; coding: utf-8 -*-
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

def _keep_data(entry):
    dest = entry[0].replace("\\\\", "/").lower()
    if "_tcl_data/tzdata/" in dest or "_tcl_data/msgs/" in dest or "_tk_data/demos/" in dest or "_tk_data/msgs/" in dest:
        return False
    return True

a.datas = [d for d in a.datas if _keep_data(d)]
pyz = PYZ(a.pure)
"""


def generate_onefile_spec(spec_path: Path) -> None:
    content = _common_analysis_block() + f"""
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
    spec_path.write_text(content, encoding="utf-8")


def generate_onedir_spec(spec_path: Path) -> None:
    content = _common_analysis_block() + f"""
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HF-Model-Downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r"{str(ICON_PATH)}",
    version=r"{str(VERSION_INFO_PATH)}",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name={PORTABLE_DIR_NAME!r},
)
"""
    spec_path.write_text(content, encoding="utf-8")


def zip_directory(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file_path in sorted(src_dir.rglob("*")):
            if file_path.is_file():
                arcname = Path(src_dir.name) / file_path.relative_to(src_dir)
                zf.write(file_path, arcname.as_posix())


def _has_low_integrity(path: Path) -> bool:
    if sys.platform != "win32" or not path.exists():
        return False
    res = subprocess.run(
        ["icacls", str(path)],
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
    )
    return "Low Mandatory Level" in res.stdout


def _ensure_medium_integrity(path: Path) -> None:
    """Try to reset Medium integrity on Windows; warn clearly if elevation is required."""
    if sys.platform != "win32" or not path.exists():
        return
    if not _has_low_integrity(path):
        return
    level = "(OI)(CI)M" if path.is_dir() else "M"
    res = subprocess.run(
        ["icacls", str(path), "/setintegritylevel", level],
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
    )
    if res.returncode == 0 and path.is_dir():
        subprocess.run(
            ["icacls", str(path), "/setintegritylevel", "M", "/T", "/Q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    elif _has_low_integrity(path):
        print(
            f"[WARNING] {path} inherited Windows 'Low Mandatory Level' from a parent folder, "
            "and elevating its integrity label requires Administrator privileges.\n"
            "          Running an EXE with Low Mandatory Level will trigger "
            "'Could not create temporary directory!'.\n"
            f'          Fix in an Administrator PowerShell: icacls "{ROOT}" /setintegritylevel "(OI)(CI)M" /T\n'
            "          Or copy the EXE to a normal folder (e.g. Downloads) before launching."
        )


def _report_artifact(label: str, path: Path) -> None:
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"  [{label}] {path.name} ({size_mb:.2f} MB)")
    print(f"    SHA-256: {sha256}")


def main() -> None:
    ensure_icon(ICON_PATH)
    print(f"[1/4] Icon ready: {ICON_PATH}")

    onefile_spec = ROOT / f"{EXE_NAME}.spec"
    onedir_spec = ROOT / f"{PORTABLE_DIR_NAME}.spec"
    generate_onefile_spec(onefile_spec)
    generate_onedir_spec(onedir_spec)

    dist_dir = ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    print(f"[2/4] Building one-file EXE ({EXE_NAME}.exe) ...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(onefile_spec)],
        cwd=str(ROOT),
        check=True,
    )

    print(f"[3/4] Building portable onedir ZIP ({PORTABLE_DIR_NAME}.zip) ...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(onedir_spec)],
        cwd=str(ROOT),
        check=True,
    )

    onefile_exe = dist_dir / f"{EXE_NAME}.exe"
    portable_dir = dist_dir / PORTABLE_DIR_NAME
    portable_zip = dist_dir / f"{PORTABLE_DIR_NAME}.zip"
    zip_directory(portable_dir, portable_zip)
    _ensure_medium_integrity(dist_dir)

    print("[4/4] All builds succeeded:")
    _report_artifact("One-File EXE", onefile_exe)
    _report_artifact("Portable ZIP", portable_zip)


if __name__ == "__main__":
    main()
