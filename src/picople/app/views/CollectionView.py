from __future__ import annotations
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QModelIndex, QUrl
from PySide6.QtWidgets import (
    QHBoxLayout, QListView, QComboBox, QLineEdit, QToolButton, QLabel, QMessageBox
)
from PySide6.QtGui import QDesktopServices

from picople.infrastructure.db import Database
from picople.app.controllers import MediaListModel
from . import SectionView


class CollectionView(SectionView):
    """
    Grilla paginada de miniaturas leyendo desde la DB cifrada.
    Filtros: Todo/Fotos/Videos + búsqueda por texto (ruta/nombre).
    """

    def __init__(self, db: Optional[Database] = None):
        super().__init__("Colección", "Todas tus fotos y videos en una grilla rápida.")
        self.db = db

        # Controles de filtro/paginación
        row = QHBoxLayout()
        row.setSpacing(8)

        self.cmb_kind = QComboBox()
        self.cmb_kind.addItems(["Todo", "Fotos", "Videos"])
        self.cmb_kind.setToolTip("Filtrar por tipo")

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filtrar por texto en ruta/nombre…")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setObjectName("SearchEdit")

        self.btn_prev = QToolButton()
        self.btn_prev.setText("◀")
        self.btn_prev.setToolTip("Página anterior")
        self.lbl_page = QLabel("Página 1/1")
        self.lbl_page.setObjectName("StatusTag")
        self.btn_next = QToolButton()
        self.btn_next.setText("▶")
        self.btn_next.setToolTip("Página siguiente")
        self.btn_reload = QToolButton()
        self.btn_reload.setText("Recargar")
        self.btn_reload.setToolTip("Recargar resultados")

        row.addWidget(self.cmb_kind)
        row.addWidget(self.txt_search, 1)
        row.addWidget(self.btn_prev)
        row.addWidget(self.lbl_page)
        row.addWidget(self.btn_next)
        row.addWidget(self.btn_reload)

        # Lista en modo iconos
        self.view = QListView()
        self.view.setViewMode(QListView.IconMode)
        self.view.setWrapping(True)
        self.view.setResizeMode(QListView.Adjust)
        self.view.setMovement(QListView.Static)
        self.view.setSpacing(12)
        self.view.setIconSize(QSize(160, 160))
        self.view.setUniformItemSizes(False)
        self.view.doubleClicked.connect(self._open_selected)

        self.model = MediaListModel(tile_size=160)
        self.view.setModel(self.model)

        # Integrar al layout de SectionView
        lay = self.layout()
        lay.addLayout(row)
        lay.addWidget(self.view, 1)

        # Estado
        self.page_size = 200
        self.page = 1
        self.total = 0
        self.total_pages = 1

        # Señales
        self.cmb_kind.currentIndexChanged.connect(self._on_filters_changed)
        self.txt_search.returnPressed.connect(self._on_filters_changed)
        self.btn_reload.clicked.connect(self._on_filters_changed)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)

        # Carga inicial
        self.refresh()

    # -------- Lógica -------- #
    def _current_kind(self) -> Optional[str]:
        i = self.cmb_kind.currentIndex()
        return {0: None, 1: "image", 2: "video"}.get(i, None)

    def _on_filters_changed(self):
        self.page = 1
        self.refresh()

    def _prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.refresh()

    def _next_page(self):
        if self.page < self.total_pages:
            self.page += 1
            self.refresh()

    def refresh(self):
        if not self.db or not self.db.is_open:
            self.model.set_items([])
            self.lbl_page.setText("DB no abierta")
            return

        kind = self._current_kind()
        search = self.txt_search.text().strip() or None

        self.total = self.db.count_media(kind=kind, search=search)
        self.total_pages = max(
            1, (self.total + self.page_size - 1) // self.page_size)
        self.page = max(1, min(self.page, self.total_pages))
        offset = (self.page - 1) * self.page_size

        items = self.db.fetch_media_page(
            offset, self.page_size, kind=kind, search=search, order_by="mtime DESC")
        self.model.set_items(items)
        self.lbl_page.setText(
            f"Página {self.page}/{self.total_pages}  •  {self.total} items")

    def _open_selected(self, index: QModelIndex):
        if not index.isValid():
            return
        item = self.model.items[index.row()]
        path = item["path"]
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception:
            QMessageBox.information(self, "Abrir", f"No se pudo abrir: {path}")
