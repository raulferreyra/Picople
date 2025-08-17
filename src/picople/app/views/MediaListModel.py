# src/picople/app/views/MediaListModel.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QAbstractListModel, QModelIndex
from PySide6.QtGui import QPixmap, QIcon, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QComboBox,
    QLineEdit, QToolButton, QLabel, QMessageBox
)
from PySide6.QtCore import QUrl

from picople.infrastructure.db import Database
from . import SectionView


# -------- Modelo de lista para miniaturas -------- #
class MediaListModel(QAbstractListModel):
    def __init__(self, tile_size: int = 160):
        super().__init__()
        self.items: list[dict] = []
        self.cache: dict[str, QPixmap] = {}
        self.tile_size = tile_size

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        i = index.row()
        if i < 0 or i >= len(self.items):
            return None
        item = self.items[i]
        if role == Qt.DisplayRole:
            return Path(item["path"]).name
        if role == Qt.DecorationRole:
            thumb = item.get("thumb_path")
            if thumb:
                pm = self.cache.get(thumb)
                if pm is None:
                    pm = QPixmap(thumb)
                    if not pm.isNull():
                        pm = pm.scaled(self.tile_size, self.tile_size,
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.cache[thumb] = pm
                if pm and not pm.isNull():
                    return QIcon(pm)
        if role == Qt.ToolTipRole:
            return item["path"]
        return None

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self.items = items
        self.endResetModel()


# -------- Vista de Colección -------- #
class CollectionView(SectionView):
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

        # Lista en IconMode
        self.view = QListView()
        self.view.setViewMode(QListView.IconMode)
        self.view.setWrapping(True)
        self.view.setResizeMode(QListView.Adjust)
        self.view.setMovement(QListView.Static)
        self.view.setSpacing(12)
        self.view.setIconSize(QSize(160, 160))
        self.view.setUniformItemSizes(False)  # permite distintos textos
        self.view.doubleClicked.connect(self._open_selected)

        self.model = MediaListModel(tile_size=160)
        self.view.setModel(self.model)

        # Layout
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

        # total y paginación
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
        # Abrir en el explorador; si quieres “select”, usamos comando Windows
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception:
            QMessageBox.information(self, "Abrir", f"No se pudo abrir: {path}")
