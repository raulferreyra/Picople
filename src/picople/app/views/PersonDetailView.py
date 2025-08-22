from __future__ import annotations
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QStackedWidget, QStyle, QInputDialog
)

from .PersonDetailHeader import PersonDetailHeader


SUG_TILE = 160  # tamaño para futuros thumbnails en “Sugerencias”


class PersonDetailView(QWidget):
    """
    Detalle de un cluster (persona/mascota):
      - Header propio con back, avatar circular, título y lápiz.
      - Link “Sugerencias” encima de la grilla principal (por ahora placeholder).
      - Stacked: Página “Todo” (futuro CollectionView filtrado) y “Sugerencias”.
    """
    requestBack = Signal()

    def __init__(self, *, cluster: Dict[str, Any], db=None, parent=None):
        super().__init__(parent)
        self.cluster = cluster
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ───────── Header
        title = cluster.get("title") or "Sin nombre"
        cover = cluster.get("cover")
        kind = cluster.get("kind", "person")
        self.header = PersonDetailHeader(
            title=title, cover=cover, kind=kind, parent=self)
        self.header.requestBack.connect(self.requestBack.emit)
        self.header.requestRename.connect(self._rename_cluster)
        root.addWidget(self.header)

        # ───────── Subheader con “Sugerencias” (enlace)
        link_row = QHBoxLayout()
        link_row.setContentsMargins(0, 0, 0, 0)
        link_row.setSpacing(8)

        self.link_sugs = QToolButton(self)
        self.link_sugs.setObjectName("ToolbarBtn")
        self.link_sugs.setText("Sugerencias")
        self.link_sugs.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.link_sugs.setCursor(Qt.PointingHandCursor)
        self.link_sugs.clicked.connect(lambda: self._stack.setCurrentIndex(1))

        link_row.addStretch(1)
        link_row.addWidget(self.link_sugs)
        root.addLayout(link_row)

        # ───────── Contenido (stacked)
        self._stack = QStackedWidget(self)
        root.addWidget(self._stack, 1)

        # Página “Todo” (placeholder ahora)
        self.page_all = QWidget(self)
        lay_all = QVBoxLayout(self.page_all)
        lay_all.setContentsMargins(0, 0, 0, 0)
        lay_all.setSpacing(0)
        lbl_all = QLabel(
            "Aquí verás todas las fotos de esta persona/mascota.\n(Pronto: grilla filtrada por cluster)", self.page_all)
        lbl_all.setAlignment(Qt.AlignCenter)
        lbl_all.setObjectName("SectionText")
        lay_all.addWidget(lbl_all, 1)

        # Página “Sugerencias” (placeholder con explicación)
        self.page_sugs = QWidget(self)
        lay_sugs = QVBoxLayout(self.page_sugs)
        lay_sugs.setContentsMargins(0, 0, 0, 0)
        lay_sugs.setSpacing(8)

        hint = QLabel(
            "Sugerencias de esta persona/mascota.\n\n"
            "Aquí aparecerán tarjetas con:\n"
            "   ✅ Confirmar  •  ❌ Rechazar  •  🗑️ No es imagen (falso positivo)\n\n"
            "Por ahora no hay sugerencias; en el siguiente paso añadimos la grilla.",
            self.page_sugs
        )
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("SectionText")
        lay_sugs.addWidget(hint, 1)

        # Volver a “Todo”
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(8)
        btn_back_all = QToolButton(self.page_sugs)
        btn_back_all.setObjectName("ToolbarBtn")
        btn_back_all.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        btn_back_all.setText("Volver")
        btn_back_all.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn_back_all.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        nav_row.addStretch(1)
        nav_row.addWidget(btn_back_all)
        lay_sugs.addLayout(nav_row)

        self._stack.addWidget(self.page_all)   # idx 0
        self._stack.addWidget(self.page_sugs)  # idx 1
        self._stack.setCurrentIndex(0)

    # ───────── acciones
    def _rename_cluster(self) -> None:
        old = self.cluster.get("title") or "Sin nombre"
        new, ok = QInputDialog.getText(self, "Renombrar", "", text=old)
        if not ok:
            return
        name = new.strip()
        if not name or name == old:
            return

        # Por ahora solo UI (cuando esté la tabla de clusters lo persistimos)
        self.cluster["title"] = name
        self.header.set_title(name)
