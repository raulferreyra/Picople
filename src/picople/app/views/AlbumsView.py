# src/picople/app/views/AlbumsView.py
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QSize, QModelIndex
from PySide6.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QToolButton, QLabel,
    QStackedWidget, QInputDialog, QMessageBox, QStyle
)

from picople.infrastructure.db import Database, DBError
from .SectionView import SectionView
from .ThumbDelegate import ThumbDelegate
from .CollectionView import CollectionView


ALBUM_ID_ROLE = Qt.UserRole + 50


class AlbumsView(SectionView):
    """
    Vista de Álbumes:
      - Página 1: grilla de álbumes (portada + título + contador)
      - Página 2: detalle del álbum (CollectionView restringida a album_id)
        con botón < Volver y lápiz para editar el título.
    """

    def __init__(self, db: Optional[Database] = None):
        super().__init__("Álbumes", "Organizados automáticamente por carpetas.", compact=True)
        self.db = db

        self.inner = QStackedWidget()
        self.content_layout.addWidget(self.inner, 1)

        # ---------- Página grilla ----------
        page_grid = QWidget()
        lg = QVBoxLayout(page_grid)
        lg.setContentsMargins(0, 0, 0, 0)
        self.list = QListView()
        self.list.setViewMode(QListView.IconMode)
        self.list.setWrapping(True)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setSpacing(12)
        self.list.setIconSize(QSize(160, 160))
        self.list.setUniformItemSizes(False)

        self.model = QStandardItemModel(self.list)
        self.list.setModel(self.model)
        self.list.setItemDelegate(ThumbDelegate(
            tile=160, text_lines=2, parent=self.list))
        self.list.doubleClicked.connect(self._open_selected)

        lg.addWidget(self.list, 1)
        self.inner.addWidget(page_grid)       # index 0

        # ---------- Página detalle ----------
        page_detail = QWidget()
        ld = QVBoxLayout(page_detail)
        ld.setContentsMargins(0, 0, 0, 0)

        # Barra superior: < Volver | Título | ✎ Editar
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 8, 8, 8)
        bar.setSpacing(8)

        self.btn_back = QToolButton()
        self.btn_back.setText("◀")
        self.btn_back.setObjectName("ToolbarBtn")
        self.btn_back.clicked.connect(self._go_back)

        self.lbl_album_title = QLabel("")
        self.lbl_album_title.setObjectName("AppTitle")

        self.btn_edit = QToolButton()
        self.btn_edit.setText("✎")
        self.btn_edit.setObjectName("ToolbarBtn")
        self.btn_edit.clicked.connect(self._edit_title)

        bar.addWidget(self.btn_back)
        bar.addWidget(self.lbl_album_title, 1)
        bar.addWidget(self.btn_edit)
        ld.addLayout(bar)

        # Colección filtrada por álbum
        self.album_view: Optional[CollectionView] = None
        self.detail_container = QWidget()
        lc = QVBoxLayout(self.detail_container)
        lc.setContentsMargins(0, 0, 0, 0)
        ld.addWidget(self.detail_container, 1)

        self.inner.addWidget(page_detail)     # index 1

        self._current_album_id: Optional[int] = None
        self.refresh()

    # -------------------- API pública -------------------- #
    def refresh(self):
        if not self.db or not self.db.is_open:
            self.model.clear()
            return
        albums = self.db.list_albums()  # [{id,title,cover_path,count}]
        self.model.clear()

        style = self.style()
        folder_icon = style.standardIcon(QStyle.SP_DirIcon)

        for a in albums:
            title = a["title"]
            cover = a.get("cover_path") or ""
            count = int(a.get("count", 0))
            text = f"{title}\n{count} elemento{'s' if count != 1 else ''}"

            item = QStandardItem(text)
            item.setEditable(False)
            item.setData(a["id"], ALBUM_ID_ROLE)

            if cover:
                pm = QPixmap(cover)
                if not pm.isNull():
                    item.setIcon(QIcon(pm))
                else:
                    item.setIcon(folder_icon)
            else:
                item.setIcon(folder_icon)

            self.model.appendRow(item)

        # grid layout size (coincidir con delegate)
        tile = 160
        fm = self.list.fontMetrics()
        cell_h = 8 + tile + 6 + fm.height()*2 + 8
        cell_w = 10 + tile + 10
        self.list.setGridSize(QSize(cell_w, cell_h))

        self.inner.setCurrentIndex(0)

    # -------------------- Handlers -------------------- #
    def _open_selected(self, idx: QModelIndex):
        if not idx.isValid():
            return
        album_id = idx.data(ALBUM_ID_ROLE)
        # título es la primera línea del DisplayRole
        text = idx.data(Qt.DisplayRole) or ""
        title = str(text).splitlines()[0] if text else "Álbum"
        self._open_album(album_id, title)

    def _open_album(self, album_id: int, title: str):
        if not self.db or not self.db.is_open:
            return
        # limpiar contenedor detalle
        if self.album_view is not None:
            self.album_view.setParent(None)
            self.album_view.deleteLater()
            self.album_view = None

        self._current_album_id = int(album_id)
        self.lbl_album_title.setText(title)

        self.album_view = CollectionView(
            db=self.db,
            title=title,
            subtitle="Fotos y videos del álbum.",
            favorites_only=False,
            album_id=self._current_album_id
        )
        self.detail_container.layout().addWidget(self.album_view)
        self.inner.setCurrentIndex(1)

    def _go_back(self):
        self.inner.setCurrentIndex(0)
        self._current_album_id = None
        # refrescar grilla por si cambió algo
        self.refresh()

    def _edit_title(self):
        if not self.db or not self.db.is_open or self._current_album_id is None:
            return
        current = self.lbl_album_title.text()
        new, ok = QInputDialog.getText(
            self, "Renombrar álbum", "Título:", text=current)
        if not ok or not new or new == current:
            return
        try:
            self.db.rename_album(self._current_album_id, new)
            self.lbl_album_title.setText(new)
        except Exception as e:
            QMessageBox.critical(self, "Álbum", f"No se pudo renombrar: {e}")
