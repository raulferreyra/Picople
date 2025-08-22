from __future__ import annotations
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, QSize, QModelIndex
from PySide6.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QLabel, QStackedWidget,
    QToolButton, QStyle, QApplication
)

from .SectionView import SectionView
from .PersonDetailView import PersonDetailView


# Data role para guardar el “cluster” (dict)
ROLE_DATA = Qt.UserRole + 500


class PeopleView(SectionView):
    """
    Vista principal de “Personas y mascotas”.
    Scaffold inicial:
      - Grilla de clusters (placeholders por ahora).
      - Doble clic → detalle del cluster.
      - Oculta el header de sección en el detalle (para no duplicar títulos).
    """

    def __init__(self) -> None:
        super().__init__("Personas y mascotas",
                         "Agrupación por caras (personas) y mascotas.",
                         compact=True, show_header=True)

        self.stack = QStackedWidget()
        self._page_list = QWidget()
        self._page_detail = QWidget()

        self._build_list_page()
        self._build_detail_page()

        self.stack.addWidget(self._page_list)     # idx 0
        self.stack.addWidget(self._page_detail)   # idx 1

        lay = self.content_layout
        lay.addWidget(self.stack, 1)

        self._reload_list()

    # ───────────────── lista ─────────────────
    def _build_list_page(self) -> None:
        root = QVBoxLayout(self._page_list)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.list = QListView()
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

        self.empty_lbl = QLabel(
            "Aún no hay personas o mascotas detectadas.\n"
            "Pronto podrás agrupar y nombrar caras aquí."
        )
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setObjectName("SectionText")
        self.empty_lbl.hide()
        root.addWidget(self.empty_lbl)

    def _reload_list(self) -> None:
        """Placeholder de clusters; luego vendrá la data real desde DB."""
        self.model.clear()

        clusters: List[Dict[str, Any]] = [
            {"id": None, "title": "Sin nombre",
                "kind": "person", "count": 0, "cover": None},
            {"id": None, "title": "Mascota",
                "kind": "pet", "count": 0, "cover": None},
        ]

        if not clusters:
            self.empty_lbl.show()
            return
        self.empty_lbl.hide()

        for c in clusters:
            title = c["title"]
            badge = " (sugerencias)" if c["count"] == 0 else f" ({c['count']})"
            txt = f"{title}{badge}"

            if c.get("cover"):
                pm = QPixmap(c["cover"])
                icon = QIcon(pm)
            else:
                sp = QStyle.SP_DialogYesButton if c["kind"] == "person" else QStyle.SP_DriveDVDIcon
                icon = self.style().standardIcon(sp)

            it = QStandardItem(icon, txt)
            it.setEditable(False)
            it.setData(c, ROLE_DATA)
            self.model.appendRow(it)

        fm = self.list.fontMetrics()
        tile = 160
        cell_h = 12 + tile + 8 + fm.height() + 8
        cell_w = 10 + tile + 10
        self.list.setGridSize(QSize(cell_w, int(cell_h)))

    # ───────────────── detalle ─────────────────
    def _build_detail_page(self) -> None:
        """Prepara el contenedor del detalle (layout único para reutilizar)."""
        self.detail_layout = QVBoxLayout(self._page_detail)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(0)

    def _open_cluster(self, idx: QModelIndex) -> None:
        data: Dict[str, Any] = idx.data(ROLE_DATA)
        if not data:
            return

        # ocultar header de la sección para evitar duplicados de título
        self.set_header_visible(False)

        detail = PersonDetailView(
            cluster=data,
            db=self._resolve_db(),
            parent=self._page_detail
        )
        detail.requestBack.connect(self._back_to_list)

        # limpiar y montar
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self.detail_layout.addWidget(detail)
        self.stack.setCurrentIndex(1)

    def _back_to_list(self) -> None:
        self.stack.setCurrentIndex(0)
        self.set_header_visible(True)

    def _resolve_db(self):
        win = QApplication.activeWindow()
        return getattr(win, "_db", None)
