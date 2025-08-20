from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex
from PySide6.QtGui import QIcon

ROLE_KIND = Qt.UserRole + 1  # usado por el delegate
ROLE_FAVORITE = Qt.UserRole + 2


class MediaListModel(QAbstractListModel):
    """
    items: lista de dicts con claves:
      - path (str)
      - kind ("image"|"video")
      - mtime (int)
      - size (int)
      - thumb_path (str|None)
    """

    def __init__(self, tile_size: int = 160, parent=None):
        super().__init__(parent)
        self.items: List[Dict[str, Any]] = []
        self.tile_size = int(tile_size)

        # Fallbacks opcionales (si el sistema/tema los ofrece)
        self._icon_image = QIcon.fromTheme("image-x-generic")
        self._icon_video = QIcon.fromTheme("video-x-generic")

    # ---- API ----
    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self.items = items or []
        self.endResetModel()

    def append_items(self, more: List[Dict[str, Any]]) -> None:
        if not more:
            return
        start = len(self.items)
        end = start + len(more) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self.items.extend(more)
        self.endInsertRows()

    def set_tile_size(self, size: int) -> None:
        self.tile_size = int(size)

    # ---- Requeridos ----
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self.items):
            return None

        it = self.items[row]

        if role == ROLE_KIND:
            return it.get("kind")
        elif role == ROLE_FAVORITE:
            return bool(it.get("favorite", False))

        if role == Qt.DisplayRole:
            # El delegate puede ocultarlo (text_lines=0)
            return it.get("path", "")

        if role == Qt.DecorationRole:
            tp = it.get("thumb_path")
            if tp and Path(tp).exists():
                return QIcon(str(tp))
            # fallback por tipo
            kind = it.get("kind")
            if kind == "video" and self._icon_video and not self._icon_video.isNull():
                return self._icon_video
            if kind == "image" and self._icon_image and not self._icon_image.isNull():
                return self._icon_image
            return None

        return None
