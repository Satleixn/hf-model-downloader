import ctypes
import json
import os
import sys
import uuid
from typing import Optional


def _get_windows_known_downloads_dir() -> Optional[str]:
    """Query Windows SHGetKnownFolderPath(FOLDERID_Downloads) via ctypes."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes

        folder_id = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        guid = GUID(
            folder_id.time_low,
            folder_id.time_mid,
            folder_id.time_hi_version,
            (ctypes.c_ubyte * 8)(*folder_id.bytes[8:]),
        )
        path_ptr = ctypes.c_wchar_p()
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
        )
        if hr == 0 and path_ptr.value:
            resolved = os.path.normpath(path_ptr.value)
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
            return resolved
    except Exception:
        return None
    return None


def get_default_downloads_dir() -> str:
    """Return the OS system default Downloads directory."""
    win_downloads = _get_windows_known_downloads_dir()
    if win_downloads and os.path.isdir(win_downloads):
        return win_downloads

    fallback = os.path.normpath(os.path.join(os.path.expanduser("~"), "Downloads"))
    if os.path.isdir(fallback):
        return fallback
    return os.path.normpath(os.path.expanduser("~"))


def get_config_path() -> str:
    """Return a writable per-user config file path that works for both scripts and frozen EXEs."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfg_dir = os.path.join(appdata, "HFModelDownloader")
    else:
        cfg_dir = os.path.join(os.path.expanduser("~"), ".config", "hf-model-downloader")
    return os.path.join(cfg_dir, "config.json")


def load_saved_dir(config_path: Optional[str] = None) -> Optional[str]:
    """Load the last user-selected save directory from config.json, or None if unset."""
    path = config_path or get_config_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        saved = data.get("save_dir")
        if isinstance(saved, str) and saved.strip():
            return os.path.normpath(saved.strip())
    except Exception:
        return None
    return None


def save_selected_dir(save_dir: str, config_path: Optional[str] = None) -> None:
    """Persist the user-selected save directory to config.json."""
    path = config_path or get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            if isinstance(existing, dict):
                data = existing
        except Exception:
            data = {}
    data["save_dir"] = os.path.normpath(save_dir.strip())
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
