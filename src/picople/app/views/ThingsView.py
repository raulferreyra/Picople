from __future__ import annotations
from .SectionView import SectionView


class ThingsView(SectionView):
    def __init__(self):
        super().__init__("Cosas", "Búsqueda por temática: camas, flores, jardín, cielo, etc.")
