from __future__ import annotations
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QSize, QModelIndex
from PySide6.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QToolButton, QLabel,
    QStackedWidget, QInputDialog, QMessageBox, QStyle
)

from picople.infrastructure.db import Database
from picople.app.views.SectionView import SectionView
from picople.app.views.CollectionView import CollectionView
from picople.app.views.AlbumDetailView import AlbumDetailView

# almacena dict {'id':int|None, 'title':str, 'is_fav':bool}
ROLE_DATA = Qt.UserRole + 100


class AlbumsView(SectionView):
    def __init__(self, db: Optional[Database] = None):
        super().__init__("Álbumes", "Organizados automáticamente por carpetas.",
                         compact=True, show_header=True)
        self.db = db

        self.stack = QStackedWidget()
        self._page_list = QWidget()
        self._page_detail = QWidget()

        self._build_list_page()
        self._build_detail_page()

        self.stack.addWidget(self._page_list)    # idx 0
        self.stack.addWidget(self._page_detail)  # idx 1

        lay = self.content_layout
        lay.addWidget(self.stack, 1)

        self._reload_list()

    # ───────────────── Página: lista ─────────────────
    def _build_list_page(self):
        root = QVBoxLayout(self._page_list)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.list = QListView()
        self.list.setViewMode(QListView.IconMode)
        self.list.setSpacing(16)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(QSize(192, 192))
        self.list.setUniformItemSizes(False)
        self.list.doubleClicked.connect(self._open_album)

        self.model = QStandardItemModel(self.list)
        self.list.setModel(self.model)
        root.addWidget(self.list, 1)

    def _reload_list(self):
        self.model.clear()
        if not self.db or not self.db.is_open:
            return

        # “Favoritos” virtual
        fav_count = self.db.count_media(favorites_only=True)
        if fav_count > 0:
            last = self.db.fetch_media_page(
                offset=0, limit=1, favorites_only=True, order_by="mtime DESC")
            cover = (last[0].get("thumb_path")
                     or last[0].get("path")) if last else None
            pm = QPixmap(cover) if cover else QPixmap()
            it = QStandardItem(QIcon(pm), f"Favoritos  ({fav_count})")
            it.setData({"id": None, "title": "Favoritos",
                       "is_fav": True}, ROLE_DATA)
            it.setEditable(False)
            # No forzamos color si confías en tu QSS; si prefieres, comenta la línea siguiente:
            # it.setForeground(QColor("#e6e8ee"))
            self.model.appendRow(it)

        # Álbumes reales
        for a in self.db.list_albums():
            title = a["title"]
            count = a["count"]
            cover = a.get("cover_path")
            pm = QPixmap(cover) if cover else QPixmap()
            it = QStandardItem(QIcon(pm), f"{title}  ({count})")
            it.setData({"id": a["id"], "title": title,
                       "is_fav": False}, ROLE_DATA)
            it.setEditable(False)
            # it.setForeground(QColor("#e6e8ee"))
            self.model.appendRow(it)

        # grid agradable a texto: alto para título+conteo
        fm = self.list.fontMetrics()
        tile = 192
        cell_h = 12 + tile + 8 + fm.height() + 8
        cell_w = 10 + tile + 10
        self.list.setGridSize(QSize(cell_w, int(cell_h)))

    def _open_album(self, idx: QModelIndex):
        data: Dict[str, Any] = idx.data(ROLE_DATA)
        if not data:
            return

        # Al entrar a detalle ocultamos el header de la sección ("Álbumes")
        self.set_header_visible(False)

        if data.get("is_fav"):
            # colección filtrada a favoritos (embed sin header propio)
            self._show_detail(
                CollectionView(
                    db=self.db,
                    title="Favoritos",
                    subtitle="Tus elementos favoritos.",
                    favorites_only=True,
                    album_id=None,
                    embedded=True,
                ),
                title="Favoritos",
                allow_rename=False,
            )
        else:
            album_id = data["id"]
            title = data["title"]
            # ya viene embebido (sin header propio)
            view = AlbumDetailView(self.db, album_id, title)
            view.coverChanged.connect(lambda _id, _p: self._reload_list())
            self._show_detail(view, title=title,
                              allow_rename=True, album_id=album_id)

    # ───────────────── Página: detalle ─────────────────
    def _build_detail_page(self):
        root = QVBoxLayout(self._page_detail)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # header con back + título + (opcional) lápiz
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(8)

        self.btn_back = QToolButton()
        self.btn_back.setObjectName("ToolbarBtn")
        self.btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_back.clicked.connect(self._go_back_to_list)

        self.lbl_title = QLabel("")
        # Usamos el mismo objectName que el header global para heredar estilos del tema
        self.lbl_title.setObjectName("SectionTitle")

        self.btn_rename = QToolButton()
        self.btn_rename.setObjectName("ToolbarBtn")
        self.btn_rename.setText("✎")
        self.btn_rename.clicked.connect(self._rename_album)

        hdr.addWidget(self.btn_back)
        hdr.addWidget(self.lbl_title, 1)
        hdr.addWidget(self.btn_rename)
        root.addLayout(hdr)

        # aquí insertaremos la vista (CollectionView / AlbumDetailView)
        self.detail_container = QStackedWidget()
        root.addWidget(self.detail_container, 1)

        self._current_album_id: Optional[int] = None

    def _go_back_to_list(self):
        # Volvemos a la grilla y restauramos el header de sección
        self.stack.setCurrentIndex(0)
        self.set_header_visible(True)

    def _show_detail(self, view_widget: QWidget, *, title: str, allow_rename: bool, album_id: Optional[int] = None):
        self._current_album_id = album_id
        self.lbl_title.setText(title)
        self.btn_rename.setVisible(allow_rename)

        # montar el widget en el container
        while self.detail_container.count():
            w = self.detail_container.widget(0)
            self.detail_container.removeWidget(w)
            w.deleteLater()
        self.detail_container.addWidget(view_widget)
        self.detail_container.setCurrentWidget(view_widget)
        self.stack.setCurrentIndex(1)

    def _rename_album(self):
        if self._current_album_id is None or not self.db:
            return
        old = self.lbl_title.text()
        # etiqueta vacía para evitar el QLabel "Título:" quemado (tema)
        new, ok = QInputDialog.getText(self, "Renombrar álbum", "", text=old)
        if not ok:
            return
        title = new.strip()
        if not title or title == old:
            return
        try:
            # renombramos; si colisiona por título UNIQUE, se verá el error
            cur = self.db.conn.cursor()
            cur.execute("UPDATE albums SET title=? WHERE id=?;",
                        (title, self._current_album_id))
            self.db.conn.commit()
            self.lbl_title.setText(title)
            self._reload_list()
        except Exception as e:
            QMessageBox.warning(self, "Álbumes", f"No se pudo renombrar: {e}")
