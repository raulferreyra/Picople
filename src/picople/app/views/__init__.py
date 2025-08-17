# src/picople/app/views/__init__.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

# ----- Base y vistas placeholder (siguen aquí) -----


class SectionView(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("SectionTitle")
        self.title_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.sub_lbl = QLabel(
            subtitle or "Vista placeholder. Funcionalidad aún no implementada.")
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setObjectName("SectionText")

        lay.addWidget(self.title_lbl)
        lay.addWidget(self.sub_lbl)
        lay.addStretch(1)


class CollectionView(SectionView):
    def __init__(self):
        super().__init__("Colección", "Todas las fotos y videos en una sola vista.")


class FavoritesView(SectionView):
    def __init__(self):
        super().__init__("Favoritos", "Tus elementos marcados como favoritos.")


class AlbumsView(SectionView):
    def __init__(self):
        super().__init__("Álbumes", "Álbumes virtuales (basados en carpetas o reglas).")


class PeopleView(SectionView):
    def __init__(self):
        super().__init__("Personas y mascotas", "Agrupación por caras (personas) y mascotas.")


class ThingsView(SectionView):
    def __init__(self):
        super().__init__("Cosas", "Búsqueda por temática: camas, flores, jardín, cielo, etc.")


class SearchView(SectionView):
    def __init__(self):
        super().__init__("Buscar", "Escribe un texto, nombre o cosa para filtrar.")


# ----- Importa la vista separada (evita colisiones de nombre) -----
from .FoldersView import FoldersView  

__all__ = [
    "SectionView", "CollectionView", "FavoritesView",
    "AlbumsView", "PeopleView", "ThingsView", "SearchView",
    "FoldersView",
]
