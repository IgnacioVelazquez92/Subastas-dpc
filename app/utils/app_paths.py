from __future__ import annotations

import os
from pathlib import Path


APP_DIRNAME = "MonitorSubastas"


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
    return get_project_root() / "app" / "db" / "schema.sql"
