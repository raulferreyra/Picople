# src/picople/core/resources.py
from __future__ import annotations
from contextlib import contextmanager
from importlib.resources import files, as_file
from pathlib import Path
from typing import Iterable, Tuple


def _existing(p: Path) -> Path | None:
    return p if p.exists() else None


def _alts_for_parts(parts: Tuple[str, ...]) -> Iterable[Tuple[str, ...]]:
    # Si te pasan ("favicon", "favicon.ico"), prueba también ("icons", "favicon.ico")
    if parts and parts[0].lower() == "favicon":
        yield ("icons", *parts[1:])
    yield parts


@contextmanager
def asset_path(*parts: str):
    """
    Devuelve un Path utilizable para un asset.
    Prioridad:
      1) Dentro del paquete:  picople/assets/<parts...>
      2) En el repo raíz:     ./assets/<parts...>
         (y alias 'favicon' -> 'icons')
    Si no existe en ningún lado, devuelve la ruta "esperada" en ./assets/<parts...>.
    """
    parts_t = tuple(parts)

    # 1) Paquete (instalable / distribuible)
    try:
        pkg_base = files("picople") / "assets"
        for alt in _alts_for_parts(parts_t):
            with as_file(pkg_base.joinpath(*alt)) as p:
                if p.exists():
                    yield Path(p)
                    return
    except Exception:
        pass

    # 2) Repo raíz (asumiendo ejecución desde el proyecto)
    cwd = Path.cwd()
    for alt in _alts_for_parts(parts_t):
        cand = _existing(cwd / "assets" / Path(*alt))
        if cand:
            yield cand
            return

    # 3) Fallback: ruta esperada en ./assets (aunque no exista aún)
    yield cwd / "assets" / Path(*parts_t)
