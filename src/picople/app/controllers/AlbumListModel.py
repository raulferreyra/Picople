# src/picople/app/controllers/AlbumListModel.py
from __future__ import annotations
from typing import List, Dict
from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex

ROLE_ID = Qt.UserRole + 101
ROLE_TITLE = Qt.UserRole + 102
ROLE_COUNT = Qt.UserRole + 103
ROLE_COVER = Qt.UserRole + 104


class AlbumListModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.items: List[Dict] = []

    def set_items(self, items: List[Dict]):
        self.beginResetModel()
        self.items = items
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def data(self, idx: QModelIndex, role: int):
        if not idx.isValid():
            return None
        it = self.items[idx.row()]
        if role == Qt.DisplayRole:
            return f"{it['title']}  ({it['count']})"
        if role == ROLE_ID:
            return it["id"]
        if role == ROLE_TITLE:
            return it["title"]
        if role == ROLE_COUNT:
            return it["count"]
        if role == ROLE_COVER:
            return it.get("cover_path")
        return None
