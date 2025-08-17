# src/picople/core/paths.py
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QStandardPaths


def app_data_dir() -> Path:
    base = Path(QStandardPaths.writableLocation(
        QStandardPaths.AppDataLocation))
    base.mkdir(parents=True, exist_ok=True)
    return base


def thumbs_dir() -> Path:
    d = app_data_dir() / "thumbs"
    d.mkdir(parents=True, exist_ok=True)
    return d
