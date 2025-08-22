from __future__ import annotations
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, QSize, QModelIndex
from PySide6.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QStackedWidget, QToolButton,
    QLabel, QStyle
)

from .SectionView import SectionView
from .PersonDetailView import PersonDetailView


ROLE_DATA = Qt.UserRole + 100
TILE = 160


class PeopleView(SectionView):
    """
    Página principal de Personas y mascotas:
      • Página de lista: clusters (mock por ahora) con conteo de sugerencias
      • Página de detalle: inserta PersonDetailView y botón “volver”
    """

    def __init__(self):
        super().__init__("Personas y mascotas", "Agrupación por caras (personas) y mascotas.",
                         compact=True, show_header=True)

        self.stack = QStackedWidget(self)
        self._page_list = QWidget(self)
        self._page_detail = QWidget(self)

        self._clusters: list[Dict[str, Any]] = self._mock_clusters()
        self._current_cluster_id: Optional[str] = None

        self._build_list_page()
        self._build_detail_page()

        self.stack.addWidget(self._page_list)    # idx 0
        self.stack.addWidget(self._page_detail)  # idx 1
        self.content_layout.addWidget(self.stack, 1)

        self._reload_list()

    # ───────────────────────── List page ─────────────────────────
    def _build_list_page(self) -> None:
        root = QVBoxLayout(self._page_list)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.list = QListView(self._page_list)
        self.list.setViewMode(QListView.IconMode)
        self.list.setSpacing(16)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(QSize(TILE, TILE))
        self.list.setUniformItemSizes(False)
        self.list.doubleClicked.connect(self._open_cluster)

        self.model = QStandardItemModel(self.list)
        self.list.setModel(self.model)

        root.addWidget(self.list, 1)

    def _reload_list(self) -> None:
        self.model.clear()
        for c in self._clusters:
            pm = QPixmap(c.get("cover") or "")
            if pm.isNull():
                # placeholder gris uniforme con círculo claro
                pm = QPixmap(TILE, TILE)
                pm.fill(Qt.gray)
            icon = QIcon(pm)
            title = c.get("title") or "Sin nombre"
            sugs = int(c.get("suggestions_count", 0))
            text = f"{title}  ({sugs})"
            it = QStandardItem(icon, text)
            it.setEditable(False)
            it.setData(c, ROLE_DATA)
            self.model.appendRow(it)

        # cuadrícula agradable: alto para título
        fm = self.list.fontMetrics()
        cell_h = 12 + TILE + 8 + fm.height() + 8
        cell_w = 10 + TILE + 10
        self.list.setGridSize(QSize(cell_w, int(cell_h)))

    def _find_model_row_by_cluster_id(self, cid: str) -> int:
        for row in range(self.model.rowCount()):
            data = self.model.item(row).data(ROLE_DATA)
            if data and str(data.get("id")) == str(cid):
                return row
        return -1

    def _update_cluster_label(self, cid: str, new_sug_count: int) -> None:
        row = self._find_model_row_by_cluster_id(cid)
        if row < 0:
            return
        it = self.model.item(row)
        data: Dict[str, Any] = it.data(ROLE_DATA)
        data["suggestions_count"] = int(new_sug_count)
        title = data.get("title") or "Sin nombre"
        it.setText(f"{title}  ({new_sug_count})")
        it.setData(data, ROLE_DATA)

    # ──────────────────────── Detail page ────────────────────────
    def _build_detail_page(self) -> None:
        root = QVBoxLayout(self._page_detail)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # Barra mínima con botón “volver” (el header visual con avatar vive en PersonDetailView)
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(8)

        self.btn_back = QToolButton(self._page_detail)
        self.btn_back.setObjectName("ToolbarBtn")
        self.btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_back.clicked.connect(self._go_back_to_list)

        lbl = QLabel("Sugerencias y elementos", self._page_detail)
        lbl.setObjectName("SectionText")

        hdr.addWidget(self.btn_back)
        hdr.addWidget(lbl, 1)

        root.addLayout(hdr)

        # Contenedor del detalle
        self.detail_container = QStackedWidget(self._page_detail)
        root.addWidget(self.detail_container, 1)

    def _go_back_to_list(self) -> None:
        # Limpia el widget embebido del detalle para evitar que “se quede pegado”
        while self.detail_container.count():
            w = self.detail_container.widget(0)
            self.detail_container.removeWidget(w)
            w.deleteLater()
        self._current_cluster_id = None
        self.stack.setCurrentIndex(0)
        self.set_header_visible(True)

    def _open_cluster(self, idx: QModelIndex) -> None:
        data: Dict[str, Any] = idx.data(ROLE_DATA)
        if not data:
            return

        self._current_cluster_id = str(data.get("id", ""))
        self.set_header_visible(False)

        # Limpia contenedor
        while self.detail_container.count():
            w = self.detail_container.widget(0)
            self.detail_container.removeWidget(w)
            w.deleteLater()

        # Inserta detalle
        detail = PersonDetailView(cluster=data, parent=self._page_detail)
        # Cuando cambie el # de sugerencias en detalle, actualiza la fila en la lista
        detail.suggestionCountChanged.connect(
            lambda n, cid=self._current_cluster_id: self._update_cluster_label(
                cid, n)
        )

        self.detail_container.addWidget(detail)
        self.detail_container.setCurrentWidget(detail)
        self.stack.setCurrentIndex(1)

    # ────────────────────────── Mock data ─────────────────────────
    def _mock_clusters(self) -> list[Dict[str, Any]]:
        # Lo mínimo para visualizar: ids, títulos y conteo de sugerencias
        # (las imágenes de cover pueden venir vacías; PersonDetailView pone avatar placeholder).
        out: list[Dict[str, Any]] = []
        for i in range(1, 9):
            out.append({
                "id": f"c{i}",
                "title": f"Persona {i}",
                "cover": "",                 # sin ruta -> usa placeholder redondo
                "suggestions": [             # cada sug: id + (thumb opcional)
                    {"id": f"c{i}-s1", "thumb": ""},
                    {"id": f"c{i}-s2", "thumb": ""},
                    {"id": f"c{i}-s3", "thumb": ""},
                ],
                "suggestions_count": 3,
            })
        return out
