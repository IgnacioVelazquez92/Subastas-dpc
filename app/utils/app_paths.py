from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIRNAME = "MonitorSubastas"


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_runtime_root() -> Path:
    """
    Devuelve la raiz desde donde deben leerse recursos empaquetados.

    - Desarrollo: raiz del repo.
    - PyInstaller: carpeta temporal `_MEIPASS`.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return get_project_root()


def get_executable_dir() -> Path:
    """
    Devuelve la carpeta donde vive el ejecutable o script principal.

    En build PyInstaller one-folder coincide con la carpeta distribuible.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_project_root()


def get_local_appdata_dir() -> Path:
    raw = os.getenv("LOCALAPPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


def get_app_data_dir() -> Path:
    path = get_local_appdata_dir() / APP_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    path = get_app_data_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_data_dir() / "monitor.db"


def get_schema_path() -> Path:
    return get_runtime_root() / "app" / "db" / "schema.sql"


def get_assets_dir() -> Path:
    return get_runtime_root() / "assets"


def get_sounds_dir() -> Path:
    return get_assets_dir() / "sounds"


def get_playwright_browsers_dir() -> Path | None:
    """
    Devuelve la carpeta con navegadores embebidos si existe.

    Se usa en builds Windows para no depender de `playwright install`.
    """
    bundled = get_runtime_root() / "playwright-browsers"
    if bundled.exists():
        return bundled
    return None


def get_bundled_chromium_executable() -> Path | None:
    """
    Busca un Chromium incluido junto al build.
    """
    browsers_dir = get_playwright_browsers_dir()
    if not browsers_dir:
        return None

    patterns = (
        "chromium-*/chrome-win64/chrome.exe",
        "chromium-*/chrome-win/chrome.exe",
    )
    for pattern in patterns:
        matches = sorted(browsers_dir.glob(pattern), reverse=True)
        if matches:
            return matches[0]
    return None
