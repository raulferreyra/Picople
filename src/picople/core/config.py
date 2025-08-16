# src/picople/core/config.py
from __future__ import annotations
from typing import List
from PySide6.QtCore import QSettings

KEY_ROOT_DIRS = "paths/roots"


def get_root_dirs() -> List[str]:
    s = QSettings()
    val = s.value(KEY_ROOT_DIRS, [])
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val]
    if isinstance(val, str):
        return [val] if val else []
    return []


def set_root_dirs(dirs: List[str]) -> None:
    s = QSettings()
    # QSettings almacena listas de cadenas sin problema
    s.setValue(KEY_ROOT_DIRS, list(dict.fromkeys(dirs)))  # sin duplicados


def add_root_dir(path: str) -> None:
    dirs = get_root_dirs()
    if path and path not in dirs:
        dirs.append(path)
        set_root_dirs(dirs)


def remove_root_dir(path: str) -> None:
    dirs = [d for d in get_root_dirs() if d != path]
    set_root_dirs(dirs)
