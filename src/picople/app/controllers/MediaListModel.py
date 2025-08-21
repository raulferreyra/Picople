from __future__ import annotations
from pathlib import Path
from typing import Any, List

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex
from PySide6.QtGui import QIcon, QPixmap


# Roles unificados
ROLE_PATH = Qt.UserRole + 1
ROLE_KIND = Qt.UserRole + 2
ROLE_FAVORITE = Qt.UserRole + 3
ROLE_THUMB = Qt.UserRole + 4


class MediaListModel(QAbstractListModel):
    """
    Mantiene una lista de dicts con claves:
      path, kind ('image'|'video'), mtime, size, thumb_path, favorite(bool)
    """

    def __init__(self, *, tile_size: int = 160, parent=None) -> None:
        super().__init__(parent)
        self.items: List[dict] = []
        self.tile_size = int(tile_size)
        self._placeholder = QPixmap(self.tile_size, self.tile_size)
        self._placeholder.fill(Qt.transparent)

    # API
    def set_items(self, items: List[dict]) -> None:
        self.beginResetModel()
        self.items = items[:] if items else []
        self.endResetModel()

    def append_items(self, items: List[dict]) -> None:
        if not items:
            return
        first = len(self.items)
        last = first + len(items) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self.items.extend(items)
        self.endInsertRows()

    def set_tile_size(self, tile: int) -> None:
        self.tile_size = int(tile)
        self._placeholder = QPixmap(self.tile_size, self.tile_size)
        self._placeholder.fill(Qt.transparent)
        # que el delegado se repinte
        self.layoutChanged.emit()

    # QAbstractListModel
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self.items):
            return None
        it = self.items[row]

        if role == Qt.DisplayRole:
            # Sólo el nombre del archivo (el delegado puede ocultarlo si así se configuró)
            return Path(it.get("path", "")).name

        if role == Qt.DecorationRole:
            # Pixmap de miniatura (o placeholder)
            tp = it.get("thumb_path")
            if tp and Path(tp).exists():
                pm = QPixmap(str(tp))
                if not pm.isNull():
                    # QIcon para que el delegado pueda pedir tamaño
                    return QIcon(pm)
            return QIcon(self._placeholder)

        if role == ROLE_PATH:
            return it.get("path")

        if role == ROLE_KIND:
            return it.get("kind")

        if role == ROLE_FAVORITE:
            return bool(it.get("favorite", False))

        if role == ROLE_THUMB:
            return it.get("thumb_path")

        return None
