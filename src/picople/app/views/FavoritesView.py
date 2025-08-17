from __future__ import annotations
from .SectionView import SectionView


class FavoritesView(SectionView):
    def __init__(self):
        super().__init__("Favoritos", "Tus elementos marcados como favoritos.")
