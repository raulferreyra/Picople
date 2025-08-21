# src/picople/app/controllers/MediaListModel.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QByteArray
from PySide6.QtGui import QIcon, QPixmap


# Roles: ÚNICA FUENTE DE VERDAD
ROLE_KIND = Qt.UserRole + 1       # "image" | "video"
ROLE_FAVORITE = Qt.UserRole + 2   # bool


class MediaListModel(QAbstractListModel):
    def __init__(self, *, tile_size: int = 160, parent=None) -> None:
        super().__init__(parent)
        self.items: List[Dict[str, Any]] = []
        self.tile_size = int(tile_size)

    # ---------- API ----------
    def set_tile_size(self, sz: int) -> None:
        self.tile_size = int(sz)
        if self.rowCount() > 0:
            top_left = self.index(0, 0)
            bottom_right = self.index(self.rowCount()-1, 0)
            self.dataChanged.emit(top_left, bottom_right, [Qt.DecorationRole])

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        # normaliza favorite -> bool
        for it in items:
            it["favorite"] = bool(it.get("favorite", False))
        self.beginResetModel()
        self.items = list(items)
        self.endResetModel()

    def append_items(self, more: List[Dict[str, Any]]) -> None:
        if not more:
            return
        start = len(self.items)
        for it in more:
            it["favorite"] = bool(it.get("favorite", False))
        self.beginInsertRows(QModelIndex(), start, start + len(more) - 1)
        self.items.extend(more)
        self.endInsertRows()

    def set_favorite_by_path(self, path: str, fav: bool) -> None:
        # actualiza un elemento y emite dataChanged SOLO para ROLE_FAVORITE
        for row, it in enumerate(self.items):
            if it.get("path") == path:
                it["favorite"] = bool(fav)
                idx = self.index(row, 0)
                self.dataChanged.emit(idx, idx, [ROLE_FAVORITE])
                break

    # ---------- Qt model ----------
    # type: ignore[override]
    def rowCount(self, _parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    # type: ignore[override]
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self.items):
            return None
        it = self.items[row]

        if role == Qt.DisplayRole:
            # si quieres ocultar texto, el delegate usa text_lines=0 y esto no se dibuja
            return it.get("path")

        if role == Qt.DecorationRole:
            pm = self._pixmap_for(it)
            if pm:
                return QIcon(pm)
            return None

        if role == ROLE_KIND:
            return it.get("kind")

        if role == ROLE_FAVORITE:
            # DEVOLVER SIEMPRE bool real
            return bool(it.get("favorite", False))

        return None

    def roleNames(self) -> dict:  # type: ignore[override]
        return {
            int(Qt.DisplayRole): QByteArray(b"display"),
            int(Qt.DecorationRole): QByteArray(b"icon"),
            int(ROLE_KIND): QByteArray(b"kind"),
            int(ROLE_FAVORITE): QByteArray(b"favorite"),
        }

    # ---------- Helpers ----------
    def _pixmap_for(self, it: Dict[str, Any]) -> Optional[QPixmap]:
        # usa thumb si existe, si no intenta cargar el path (cuidado videos)
        thumb = it.get("thumb_path")
        path = it.get("path")
        size = self.tile_size or 160

        def _load(p: Optional[str]) -> Optional[QPixmap]:
            if not p:
                return None
            qpm = QPixmap(p)
            if qpm.isNull():
                return None
            if qpm.width() != size or qpm.height() != size:
                qpm = qpm.scaled(size, size, Qt.KeepAspectRatio,
                                 Qt.SmoothTransformation)
            return qpm

        pm = _load(thumb)
        if pm:
            return pm

        # último recurso: NO intentes cargar video directo
        if it.get("kind") == "image":
            return _load(path)

        return None
