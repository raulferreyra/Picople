from __future__ import annotations
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, QSize, QModelIndex
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListView, QStackedWidget, QStyle
)

from .SectionView import SectionView
from .PersonDetailView import PersonDetailView

ROLE_DATA = Qt.UserRole + 100


class PeopleView(SectionView):
    """
    Lista de clusters (personas/mascotas) en grilla.
    - Doble click abre PersonDetailView (con su header local).
    - Se oculta el header de sección global al entrar a detalle para evitar títulos duplicados.
    - Datos "mock" por ahora (sin DB).
    """

    def __init__(self):
        super().__init__("Personas y mascotas",
                         "Agrupación por caras (personas) y mascotas.", compact=True)

        self.stack = QStackedWidget()
        self._page_list = QWidget()
        self._page_detail = QWidget()
        self.detail_container: QStackedWidget | None = None
        self._current_detail: Optional[PersonDetailView] = None

        self._build_list_page()
        self._build_detail_page()

        self.stack.addWidget(self._page_list)    # idx 0
        self.stack.addWidget(self._page_detail)  # idx 1

        lay = self.content_layout
        lay.addWidget(self.stack, 1)

        self._reload_list()

    # ───────────────── Página lista ─────────────────
    def _build_list_page(self) -> None:
        root = QVBoxLayout(self._page_list)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.list = QListView(self._page_list)
        self.list.setViewMode(QListView.IconMode)
        self.list.setSpacing(16)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(QSize(160, 160))
        self.list.setUniformItemSizes(False)
        self.list.doubleClicked.connect(self._open_cluster)

        self.model = QStandardItemModel(self.list)
        self.list.setModel(self.model)
        root.addWidget(self.list, 1)

    # ───────────────── Página detalle (contenedor fijo) ─────────────────
    def _build_detail_page(self) -> None:
        root = QVBoxLayout(self._page_detail)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.detail_container = QStackedWidget(self._page_detail)
        root.addWidget(self.detail_container, 1)

    def _reload_list(self) -> None:
        self.model.clear()

        clusters = self._mock_clusters()

        for cl in clusters:
            title = cl["title"]
            count = cl.get("count", 0)
            sp = QStyle.SP_DirIcon if cl.get(
                "kind") == "person" else QStyle.SP_DriveDVDIcon
            pm = self.style().standardIcon(sp).pixmap(160, 160)
            it = QStandardItem(QIcon(pm), f"{title}  ({count})")
            it.setEditable(False)
            it.setData(cl, ROLE_DATA)
            self.model.appendRow(it)

        fm = self.list.fontMetrics()
        tile = 160
        cell_h = 12 + tile + 8 + fm.height() + 8
        cell_w = 10 + tile + 10
        self.list.setGridSize(QSize(cell_w, int(cell_h)))

    def _open_cluster(self, idx: QModelIndex) -> None:
        data: Dict[str, Any] = idx.data(ROLE_DATA)
        if not data:
            return

        # Oculta header de sección global para evitar doble título
        if hasattr(self, "set_header_visible"):
            self.set_header_visible(False)

        detail = PersonDetailView(cluster=data, parent=self._page_detail)
        detail.requestBack.connect(self._back_to_list)

        self._current_detail = detail
        self._mount_detail(detail)
        self.stack.setCurrentIndex(1)

    def _mount_detail(self, widget: QWidget) -> None:
        if not self.detail_container:
            return
        while self.detail_container.count():
            w = self.detail_container.widget(0)
            self.detail_container.removeWidget(w)
            if w:
                w.deleteLater()
        self.detail_container.addWidget(widget)
        self.detail_container.setCurrentWidget(widget)

    def _back_to_list(self) -> None:
        self.stack.setCurrentIndex(0)
        if hasattr(self, "set_header_visible"):
            self.set_header_visible(True)
        self._current_detail = None
        if self.detail_container:
            while self.detail_container.count():
                w = self.detail_container.widget(0)
                self.detail_container.removeWidget(w)
                if w:
                    w.deleteLater()

    # ───────────────── Mock data ─────────────────
    def _mock_clusters(self) -> List[Dict[str, Any]]:
        def mk_sugs(n: int) -> List[Dict[str, Any]]:
            # thumb None = placeholder; id único
            return [{"id": f"sug_{i}", "thumb": None} for i in range(n)]

        return [
            {"id": 1, "title": "Sin nombre", "kind": "person",
                "cover": None, "count": 42,  "suggestions": mk_sugs(6)},
            {"id": 2, "title": "Matías",     "kind": "person",
                "cover": None, "count": 127, "suggestions": mk_sugs(4)},
            {"id": 3, "title": "Valentina",  "kind": "person",
                "cover": None, "count": 69,  "suggestions": mk_sugs(8)},
            {"id": 4, "title": "Bowie",      "kind": "pet",
                "cover": None, "count": 35,  "suggestions": mk_sugs(5)},
            {"id": 5, "title": "Abuela",     "kind": "person",
                "cover": None, "count": 203, "suggestions": mk_sugs(3)},
        ]
