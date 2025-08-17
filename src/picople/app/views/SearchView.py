from __future__ import annotations
from .SectionView import SectionView


class SearchView(SectionView):
    def __init__(self):
        super().__init__("Buscar", "Escribe un texto, nombre o cosa para filtrar.")
