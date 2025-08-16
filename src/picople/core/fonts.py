# src/picople/core/fonts.py
from __future__ import annotations
from typing import List
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from .resources import asset_path

# Intenta cargar variantes de Orgon si existen


def load_orgon_and_set_default(point_size: int = 13) -> None:
    app = QApplication.instance()
    if app is None:
        return

    candidates: List[str] = [
        "Orgon-Regular.ttf", "Orgon-Regular.otf",
        "Orgon-Bold.ttf",    "Orgon-Bold.otf",
        "Orgon-Light.ttf",   "Orgon-Light.otf",
        "Orgon-Medium.ttf",  "Orgon-Medium.otf",
    ]

    loaded_families: List[str] = []

    for fname in candidates:
        try:
            with asset_path("fonts", fname) as fpath:
                if fpath.exists():
                    fid = QFontDatabase.addApplicationFont(str(fpath))
                    if fid != -1:
                        fams = QFontDatabase.applicationFontFamilies(fid)
                        loaded_families.extend(list(fams))
        except Exception:
            # Silencioso: si falla, seguimos con fallback del sistema
            pass

    # Elige la primera familia válida que haya entrado
    family = loaded_families[0] if loaded_families else None
    if family:
        app.setFont(QFont(family, point_size))
    # Si no hay Orgon, el sistema mantiene la fuente por defecto (nada se rompe)
