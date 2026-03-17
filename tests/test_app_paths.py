from __future__ import annotations

from pathlib import Path

from app.utils import app_paths


def test_get_bundled_chromium_executable_prefers_latest(monkeypatch, tmp_path: Path):
    older = tmp_path / "playwright-browsers" / "chromium-1000" / "chrome-win64"
    newer = tmp_path / "playwright-browsers" / "chromium-1208" / "chrome-win64"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "chrome.exe").write_text("", encoding="utf-8")
    (newer / "chrome.exe").write_text("", encoding="utf-8")

    monkeypatch.setattr(app_paths, "get_runtime_root", lambda: tmp_path)

    resolved = app_paths.get_bundled_chromium_executable()

    assert resolved == newer / "chrome.exe"


def test_get_schema_path_uses_runtime_root(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "bundle"
    monkeypatch.setattr(app_paths, "get_runtime_root", lambda: runtime_root)

    assert app_paths.get_schema_path() == runtime_root / "app" / "db" / "schema.sql"
