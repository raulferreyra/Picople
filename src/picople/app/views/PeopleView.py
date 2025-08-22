from __future__ import annotations
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, QSize, QModelIndex
from PySide6.QtGui import (
    QIcon, QPixmap, QStandardItem, QStandardItemModel,
    QPainter
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListView, QLabel, QStackedWidget,
    QStyle, QApplication
)

from .SectionView import SectionView
from .PersonDetailView import PersonDetailView


# Data role para guardar el “cluster” (dict)
ROLE_DATA = Qt.UserRole + 500

# Tamaño único para TODOS los tiles (con o sin cover)
TILE = 160


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
        self.list.setIconSize(QSize(TILE, TILE))  # ← tamaño unificado
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

            pm_tile = self._make_tile_pixmap(
                TILE, c.get("cover"), c.get("kind", "person"))
            it = QStandardItem(QIcon(pm_tile), txt)
            it.setEditable(False)
            it.setData(c, ROLE_DATA)
            self.model.appendRow(it)

        fm = self.list.fontMetrics()
        cell_h = 12 + TILE + 8 + fm.height() + 8
        cell_w = 10 + TILE + 10
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

    # ───────────────── helpers ─────────────────
    def _make_tile_pixmap(self, size_px: int, cover_path: Optional[str], kind: str) -> QPixmap:
        """
        Devuelve SIEMPRE un pixmap cuadrado size_px × size_px.
        - Con cover: center-crop y suavizado.
        - Sin cover: placeholder de tamaño fijo con ícono centrado.
        """
        size = QSize(size_px, size_px)

        # Con cover → center-crop
        if cover_path:
            src = QPixmap(cover_path)
            if not src.isNull():
                scaled = src.scaled(
                    size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                # recorte centrado
                x = (scaled.width() - size.width()) // 2
                y = (scaled.height() - size.height()) // 2
                return scaled.copy(x, y, size.width(), size.height())

        # Sin cover → placeholder uniforme
        pm = QPixmap(size)
        pm.fill(Qt.transparent)

        pal = self.palette()
        bg = pal.window().color()
        fg = pal.text().color()

        painter = QPainter(pm)
        painter.setRenderHints(QPainter.Antialiasing |
                               QPainter.SmoothPixmapTransform)

        # Fondo con leve contraste respecto al tema
        bg_adj = bg.lighter(105) if bg.value() < 128 else bg.darker(105)
        painter.fillRect(0, 0, size.width(), size.height(), bg_adj)

        # Marco sutil
        frame = fg if fg.alpha() > 0 else pal.mid().color()
        frame.setAlpha(40)
        painter.setPen(frame)
        painter.drawRect(0, 0, size.width()-1, size.height()-1)

        # Ícono centrado
        sp = QStyle.SP_DialogYesButton if kind == "person" else QStyle.SP_DriveDVDIcon
        icon_pm = self.style().standardIcon(sp).pixmap(
            int(size_px * 0.5), int(size_px * 0.5))
        ix = (size.width() - icon_pm.width()) // 2
        iy = (size.height() - icon_pm.height()) // 2
        painter.drawPixmap(ix, iy, icon_pm)

        painter.end()
        return pm
