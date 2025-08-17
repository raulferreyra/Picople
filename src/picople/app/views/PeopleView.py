from __future__ import annotations
from .SectionView import SectionView


class PeopleView(SectionView):
    def __init__(self):
        super().__init__("Personas y mascotas", "Agrupación por caras (personas) y mascotas.")
