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
from .SectionView import SectionView


class CollectionView(SectionView):
    """
    Grilla con scroll infinito leyendo desde la DB cifrada.
    Filtros: Todo/Fotos/Videos + búsqueda por texto (ruta/nombre).
    """

    def __init__(self, db: Optional[Database] = None):
        super().__init__("Colección", "Todas tus fotos y videos en una grilla rápida.", compact=True)
        self.db = db

        # Controles de filtro (con estilos por tema mediante objectName)
        row = QHBoxLayout()
        row.setSpacing(8)

        self.cmb_kind = QComboBox()
        self.cmb_kind.setObjectName("FilterCombo")
        self.cmb_kind.addItems(["Todo", "Fotos", "Videos"])
        self.cmb_kind.setToolTip("Filtrar por tipo")

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("SearchEdit")
        self.txt_search.setPlaceholderText("Filtrar por texto en ruta/nombre…")
        self.txt_search.setClearButtonEnabled(True)

        self.btn_reload = QToolButton()
        self.btn_reload.setObjectName("FilterBtn")
        self.btn_reload.setText("Recargar")
        self.btn_reload.setToolTip("Recargar resultados")

        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("StatusTag")

        row.addWidget(self.cmb_kind)
        row.addWidget(self.txt_search, 1)
        row.addWidget(self.btn_reload)
        row.addWidget(self.lbl_info)

        # Lista en modo iconos (mismo look que 'Carpetas' por QSS)
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

        lay = self.layout()
        lay.addLayout(row)
        lay.addWidget(self.view, 1)

        # Estado: scroll infinito
        self.batch = 200
        self.offset = 0
        self.loading = False
        self.has_more = True
        self.total = 0

        # Señales
        self.cmb_kind.currentIndexChanged.connect(self._on_filters_changed)
        self.txt_search.returnPressed.connect(self._on_filters_changed)
        self.btn_reload.clicked.connect(self._on_filters_changed)
        self.view.verticalScrollBar().valueChanged.connect(self._maybe_fetch_more)

        # Carga inicial
        self.refresh(reset=True)

    # -------- Lógica -------- #
    def _current_kind(self) -> Optional[str]:
        i = self.cmb_kind.currentIndex()
        return {0: None, 1: "image", 2: "video"}.get(i, None)

    def _on_filters_changed(self):
        self.refresh(reset=True)

    def refresh(self, *, reset: bool = False):
        if not self.db or not self.db.is_open:
            self.model.set_items([])
            self.lbl_info.setText("DB no abierta")
            return

        if reset:
            self.offset = 0
            self.has_more = True
            self.loading = False
            self.total = self.db.count_media(
                kind=self._current_kind(), search=self._search_text())
            self.model.set_items([])

        # primera carga
        self._fetch_more(initial=True)

    def _fetch_more(self, initial: bool = False):
        if self.loading or not self.has_more:
            return
        self.loading = True

        kind = self._current_kind()
        items = self.db.fetch_media_page(
            offset=self.offset,
            limit=self.batch,
            kind=kind,
            search=self._search_text(),
            order_by="mtime DESC",
        )
        self.offset += len(items)
        # si trajo lote completo, probablemente hay más
        self.has_more = len(items) == self.batch

        if initial:
            self.model.set_items(items)
        else:
            self.model.append_items(items)

        # info
        shown = len(self.model.items)
        if self.total:
            self.lbl_info.setText(f"Mostrando {shown}/{self.total}")
        else:
            self.lbl_info.setText(f"Mostrando {shown}")

        self.loading = False

    def _maybe_fetch_more(self, value: int):
        sb = self.view.verticalScrollBar()
        # cuando estamos cerca del fondo (a 80px)
        if sb.maximum() - value <= 80:
            self._fetch_more(initial=False)

    def _search_text(self) -> Optional[str]:
        t = self.txt_search.text().strip()
        return t or None

    def _open_selected(self, index: QModelIndex):
        if not index.isValid():
            return
        item = self.model.items[index.row()]
        path = item["path"]
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception:
            QMessageBox.information(self, "Abrir", f"No se pudo abrir: {path}")

    def apply_runtime_settings(self, cfg: dict):
        tile = int(cfg.get("collection/tile_size", 160))
        batch = int(cfg.get("collection/batch", self.batch))
        self.view.setIconSize(QSize(tile, tile))
        self.model.set_tile_size(tile)
        if batch != self.batch:
            self.batch = batch
            self.refresh(reset=True)
