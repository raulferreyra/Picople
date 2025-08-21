from __future__ import annotations
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from picople.infrastructure.db import Database
from picople.app.views.CollectionView import CollectionView


class AlbumDetailView(CollectionView):
    coverChanged = Signal(int, str)   # album_id, new_cover_path (thumb o path)

    def __init__(self, db: Optional[Database], album_id: int, title: str):
        super().__init__(
            db=db,
            title=title,
            subtitle="Fotos y videos del álbum.",
            favorites_only=False,
            album_id=album_id,
        )
        self.album_id = album_id

    # Menú contextual sobre miniatura
    def contextMenuEvent(self, e):
        idx = self.view.indexAt(e.pos() - self.view.pos())
        if not idx.isValid():
            return
        it = self.model.items[idx.row()]
        path = it.get("path")
        thumb = it.get("thumb_path") or path
        m = QMenu(self)
        act_cover = QAction("Elegir foto de portada", self)
        m.addAction(act_cover)

        def _set_cover():
            try:
                if self.db and self.db.is_open:
                    self.db.set_album_cover(self.album_id, thumb)
                    self.coverChanged.emit(self.album_id, thumb)
            except Exception:
                pass

        act_cover.triggered.connect(_set_cover)
        m.exec(self.mapToGlobal(e.pos()))
