from __future__ import annotations
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QModelIndex
from PySide6.QtGui import QIcon, QPixmap, QAction, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QStackedWidget, QStyle,
    QListView, QMenu, QInputDialog
)

from .PersonDetailHeader import PersonDetailHeader

SUG_TILE = 160  # tamaño de miniatura en "Sugerencias"
ROLE_DATA = Qt.UserRole + 100


class PersonDetailView(QWidget):
    """
    Detalle de un cluster (persona/mascota):
      - Header propio con back, avatar circular, título y lápiz.
      - Link “Sugerencias” encima de la grilla principal.
      - Stacked: Página “Todo” (placeholder) y “Sugerencias” (grilla con menú contextual).
    """
    requestBack = Signal()

    def __init__(self, *, cluster: Dict[str, Any], db=None, parent=None):
        super().__init__(parent)
        self.cluster = cluster
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ───────── Header
        title = cluster.get("title") or "Sin nombre"
        cover = cluster.get("cover")
        kind = cluster.get("kind", "person")
        self.header = PersonDetailHeader(
            title=title, cover=cover, kind=kind, parent=self)
        self.header.requestBack.connect(self.requestBack.emit)
        self.header.requestRename.connect(self._rename_cluster)
        root.addWidget(self.header)

        # ───────── Subheader con “Sugerencias”
        link_row = QHBoxLayout()
        link_row.setContentsMargins(0, 0, 0, 0)
        link_row.setSpacing(8)

        self.link_sugs = QToolButton(self)
        self.link_sugs.setObjectName("ToolbarBtn")
        self.link_sugs.setText("Sugerencias")
        self.link_sugs.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.link_sugs.setCursor(Qt.PointingHandCursor)
        self.link_sugs.clicked.connect(lambda: self._stack.setCurrentIndex(1))

        link_row.addStretch(1)
        link_row.addWidget(self.link_sugs)
        root.addLayout(link_row)

        # ───────── Contenido (stacked)
        self._stack = QStackedWidget(self)
        root.addWidget(self._stack, 1)

        # Página “Todo” (placeholder por ahora)
        self.page_all = QWidget(self)
        lay_all = QVBoxLayout(self.page_all)
        lay_all.setContentsMargins(0, 0, 0, 0)
        lay_all.setSpacing(0)
        lbl_all = QLabel(
            "Aquí verás todas las fotos de esta persona/mascota.\n(Pronto: grilla filtrada por cluster)", self.page_all)
        lbl_all.setAlignment(Qt.AlignCenter)
        lbl_all.setObjectName("SectionText")
        lay_all.addWidget(lbl_all, 1)

        # Página “Sugerencias”: grilla real (mock)
        self.page_sugs = QWidget(self)
        lay_sugs = QVBoxLayout(self.page_sugs)
        lay_sugs.setContentsMargins(0, 0, 0, 0)
        lay_sugs.setSpacing(8)

        self.sug_list = QListView(self.page_sugs)
        self.sug_list.setViewMode(QListView.IconMode)
        self.sug_list.setWrapping(True)
        self.sug_list.setResizeMode(QListView.Adjust)
        self.sug_list.setMovement(QListView.Static)
        self.sug_list.setSpacing(12)
        self.sug_list.setIconSize(QSize(SUG_TILE, SUG_TILE))
        self.sug_list.setUniformItemSizes(False)
        self.sug_list.doubleClicked.connect(self._confirm_suggestion)
        self.sug_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sug_list.customContextMenuRequested.connect(
            self._ctx_menu_suggestion)

        self.sug_model = QStandardItemModel(self.sug_list)
        self.sug_list.setModel(self.sug_model)
        lay_sugs.addWidget(self.sug_list, 1)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(8)
        btn_back_all = QToolButton(self.page_sugs)
        btn_back_all.setObjectName("ToolbarBtn")
        btn_back_all.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        btn_back_all.setText("Volver")
        btn_back_all.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn_back_all.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        nav_row.addStretch(1)
        nav_row.addWidget(btn_back_all)
        lay_sugs.addLayout(nav_row)

        self._stack.addWidget(self.page_all)   # idx 0
        self._stack.addWidget(self.page_sugs)  # idx 1
        self._stack.setCurrentIndex(0)

        self._load_suggestions(cluster.get("suggestions", []))

    # ───────── carga de sugerencias (mock)
    def _load_suggestions(self, sugs: List[Dict[str, Any]]) -> None:
        self.sug_model.clear()
        for s in sugs:
            thumb = s.get("thumb")
            if thumb:
                pm = QPixmap(thumb).scaled(SUG_TILE, SUG_TILE,
                                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                icon = self.style().standardIcon(QStyle.SP_FileIcon)
                pm = icon.pixmap(SUG_TILE, SUG_TILE)
            it = QStandardItem(QIcon(pm), "")
            it.setEditable(False)
            it.setData(s, ROLE_DATA)
            self.sug_model.appendRow(it)

        tile = SUG_TILE
        cell_h = 8 + tile + 8
        cell_w = 10 + tile + 10
        self.sug_list.setGridSize(QSize(cell_w, int(cell_h)))

    # ───────── acciones de contexto / doble click
    def _ctx_menu_suggestion(self, pos: QPoint) -> None:
        idx = self.sug_list.indexAt(pos)
        if not idx.isValid():
            return
        m = QMenu(self.sug_list)
        act_ok = QAction("Confirmar (agregar a la persona)", m)
        act_no = QAction("Rechazar (no es esta persona)", m)
        act_trash = QAction("No es imagen / falso positivo", m)

        act_ok.triggered.connect(lambda: self._confirm_suggestion(idx))
        act_no.triggered.connect(lambda: self._reject_suggestion(idx))
        act_trash.triggered.connect(lambda: self._trash_suggestion(idx))

        m.exec(self.sug_list.mapToGlobal(pos))

    def _confirm_suggestion(self, idx: QModelIndex) -> None:
        if not idx.isValid():
            return
        self.sug_model.removeRow(idx.row())
        # TODO: mover a "miembros confirmados" cuando exista la DB

    def _reject_suggestion(self, idx: QModelIndex) -> None:
        if not idx.isValid():
            return
        self.sug_model.removeRow(idx.row())
        # TODO: marcar como negativo para este cluster

    def _trash_suggestion(self, idx: QModelIndex) -> None:
        if not idx.isValid():
            return
        self.sug_model.removeRow(idx.row())
        # TODO: registrar como falso positivo (no imagen)

    # ───────── renombrar cluster (solo UI por ahora)
    def _rename_cluster(self) -> None:
        old = self.cluster.get("title") or "Sin nombre"
        new, ok = QInputDialog.getText(self, "Renombrar", "", text=old)
        if not ok:
            return
        name = new.strip()
        if not name or name == old:
            return
        self.cluster["title"] = name
        self.header.set_title(name)
