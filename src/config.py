import json
import os
from typing import Optional


def get_default_downloads_dir() -> str:
    """Return the user's Downloads directory (C:\\Users\\<User>\\Downloads on Windows)."""
    return os.path.normpath(os.path.join(os.path.expanduser("~"), "Downloads"))


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
