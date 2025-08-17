from __future__ import annotations
from pathlib import Path
from typing import List, Dict

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from PySide6.QtGui import QPixmap, QIcon


class MediaListModel(QAbstractListModel):
    """
    Modelo simple para miniaturas de la colección.
    items: lista de dicts con keys: path, kind, mtime, size, thumb_path
    """

    def __init__(self, tile_size: int = 160):
        super().__init__()
        self.items: List[Dict] = []
        self.cache: Dict[str, QPixmap] = {}
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

    # API
    def set_items(self, items: List[Dict]) -> None:
        self.beginResetModel()
        self.items = items
        self.endResetModel()

    def append_items(self, items: List[Dict]) -> None:
        if not items:
            return
        start = len(self.items)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        self.items.extend(items)
        self.endInsertRows()

    def set_tile_size(self, size: int) -> None:
        self.tile_size = size  # los iconos se reescalan al pedirse
