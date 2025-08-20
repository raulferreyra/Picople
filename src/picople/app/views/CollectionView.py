# src/picople/app/views/CollectionView.py
from __future__ import annotations
from typing import Optional
from pathlib import Path

from PySide6.QtCore import QSize, QModelIndex
from PySide6.QtWidgets import (
    QHBoxLayout, QListView, QComboBox, QLineEdit, QToolButton, QLabel, QApplication
)

from picople.infrastructure.db import Database
from picople.app.controllers import MediaListModel, MediaItem
from .MediaViewerPanel import MediaViewerPanel
from .SectionView import SectionView
from .ThumbDelegate import ThumbDelegate


class CollectionView(SectionView):
    """
    Grilla con scroll infinito leyendo desde la DB cifrada.
    Permite:
      - Filtro por tipo (Todo/Fotos/Videos)
      - Búsqueda por texto
      - Restricción a favoritos o a un álbum específico
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        title: str = "Colección",
        subtitle: str = "Todas tus fotos y videos en una grilla rápida.",
        favorites_only: bool = False,
        album_id: Optional[int] = None
    ):
        super().__init__(title, subtitle, compact=True)
        self.db = db
        self.favorites_only = favorites_only
        self.album_id = album_id

        # Controles de filtro
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

        # Lista modo iconos
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

        tile = int(self.model.tile_size)
        self.delegate = ThumbDelegate(
            tile=tile, text_lines=0, parent=self.view)
        self.view.setItemDelegate(self.delegate)

        fm = self.view.fontMetrics()
        cell_h = 8 + tile + 6 + (fm.height()*0) + 8
        cell_w = 10 + tile + 10
        self.view.setGridSize(QSize(cell_w, int(cell_h)))

        lay = self.content_layout
        lay.addLayout(row)
        lay.addWidget(self.view, 1)

        # Estado scroll
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
                kind=self._current_kind(),
                search=self._search_text(),
                favorites_only=self.favorites_only,
                album_id=self.album_id
            )
            self.model.set_items([])
        self._fetch_more(initial=True)

    def _fetch_more(self, initial: bool = False):
        if self.loading or not self.has_more:
            return
        self.loading = True
        items = self.db.fetch_media_page(
            offset=self.offset,
            limit=self.batch,
            kind=self._current_kind(),
            search=self._search_text(),
            order_by="mtime DESC",
            favorites_only=self.favorites_only,
            album_id=self.album_id
        )
        self.offset += len(items)
        self.has_more = len(items) == self.batch

        if initial:
            self.model.set_items(items)
        else:
            self.model.append_items(items)

        shown = len(self.model.items)
        self.lbl_info.setText(
            f"Mostrando {shown}/{self.total}" if self.total else f"Mostrando {shown}"
        )
        self.loading = False

    def _maybe_fetch_more(self, value: int):
        sb = self.view.verticalScrollBar()
        if sb.maximum() - value <= 80:
            self._fetch_more(initial=False)

    def _search_text(self) -> Optional[str]:
        t = self.txt_search.text().strip()
        return t or None

    def _open_selected(self, index: QModelIndex):
        if not index.isValid():
            return
        items = [
            MediaItem(
                path=it["path"],
                kind=it["kind"],
                mtime=it["mtime"],
                size=it["size"],
                thumb_path=it.get("thumb_path"),
                favorite=bool(it.get("favorite", False)),
            )
            for it in self.model.items
        ]
        start_idx = index.row()
        # visor embebido
        win = QApplication.activeWindow()
        viewer = MediaViewerPanel(
            items, start_idx, db=getattr(win, "_db", None), parent=win)
        # reemplaza central por visor
        win._open_viewer_embedded_from(viewer)

    def apply_runtime_settings(self, cfg: dict):
        tile = int(cfg.get("collection/tile_size", 160))
        batch = int(cfg.get("collection/batch", self.batch))
        self.delegate.tile = tile
        fm = self.view.fontMetrics()
        cell_h = 8 + tile + 6 + (fm.height()*0) + 8
        cell_w = 10 + tile + 10
        self.view.setGridSize(QSize(cell_w, int(cell_h)))
        self.view.viewport().update()
        self.view.setIconSize(QSize(tile, tile))
        self.model.set_tile_size(tile)
        if batch != self.batch:
            self.batch = batch
            self.refresh(reset=True)
