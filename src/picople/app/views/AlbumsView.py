from __future__ import annotations
from .SectionView import SectionView


class AlbumsView(SectionView):
    def __init__(self):
        super().__init__("Álbumes", "Álbumes virtuales (basados en carpetas o reglas).")
