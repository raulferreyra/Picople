from __future__ import annotations
from pathlib import Path
from typing import Any, List

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex
from PySide6.QtGui import QIcon, QPixmap


ROLE_ID = Qt.UserRole + 1
ROLE_TITLE = Qt.UserRole + 2
ROLE_COUNT = Qt.UserRole + 3
ROLE_COVER = Qt.UserRole + 4


class AlbumListModel(QAbstractListModel):
    """
    items: dicts con {id, title, cover_path, count}
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.items: List[dict] = []
        self._ph = QPixmap(240, 240)
        self._ph.fill(Qt.transparent)

    def set_items(self, items: List[dict]) -> None:
        self.beginResetModel()
        self.items = items[:] if items else []
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        it = self.items[index.row()]

        if role == Qt.DisplayRole:
            return it.get("title", "")

        if role == Qt.DecorationRole:
            cp = it.get("cover_path")
            if cp and Path(cp).exists():
                pm = QPixmap(str(cp))
                if not pm.isNull():
                    return QIcon(pm)
            return QIcon(self._ph)

        if role == ROLE_ID:
            return it.get("id")
        if role == ROLE_TITLE:
            return it.get("title")
        if role == ROLE_COUNT:
            return it.get("count", 0)
        if role == ROLE_COVER:
            return it.get("cover_path")

        return None
