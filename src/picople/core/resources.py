# src/picople/core/resources.py
from __future__ import annotations
from contextlib import contextmanager
from importlib.resources import files, as_file
from pathlib import Path

# Devuelve un path utilizable en disco para un asset dentro de picople/assets/...


@contextmanager
def asset_path(*parts: str):
    # parts p.ej.: ("fonts", "Orgon-Regular.ttf") o ("icons", "app.ico")
    res = files("picople") / "assets"
    for p in parts:
        res = res / p
    # as_file maneja assets empaquetados/embebidos si más adelante usamos recursos
    with as_file(res) as p:
        yield Path(p)
