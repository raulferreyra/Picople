# src/picople/app/views/PersonDetailView.py
from __future__ import annotations
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QStackedWidget,
    QScrollArea, QGridLayout, QSizePolicy, QFrame
)

TILE = 160          # lado de miniatura cuadrada
TILE_BTN_H = 28     # alto de la fila de botones
TILE_MARGIN = 8


class SuggestionTile(QWidget):
    """
    Tile de sugerencia con:
      - Thumb cuadrado (TILE x TILE)
      - Fila de botones: ✔  ✖
      - Botón 🗑 en esquina superior derecha (overlay)
    """
    acceptClicked = Signal(str)     # id
    rejectClicked = Signal(str)     # id
    discardClicked = Signal(str)    # id

    def __init__(self, sug_id: str, thumb_path: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.sug_id = sug_id
        self.thumb_path = thumb_path

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(TILE + 2*TILE_MARGIN, TILE +
                          TILE_BTN_H + 2*TILE_MARGIN)

        root = QVBoxLayout(self)
        root.setContentsMargins(TILE_MARGIN, TILE_MARGIN,
                                TILE_MARGIN, TILE_MARGIN)
        root.setSpacing(6)

        # Thumb
        self.lbl_img = QLabel(self)
        self.lbl_img.setFixedSize(TILE, TILE)
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self._load_thumb()

        # Botonera
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.btn_ok = QToolButton(self)
        self.btn_ok.setObjectName("ToolbarBtn")
        self.btn_ok.setText("✔")
        self.btn_ok.clicked.connect(
            lambda: self.acceptClicked.emit(self.sug_id))

        self.btn_no = QToolButton(self)
        self.btn_no.setObjectName("ToolbarBtn")
        self.btn_no.setText("✖")
        self.btn_no.clicked.connect(
            lambda: self.rejectClicked.emit(self.sug_id))

        row.addWidget(self.btn_ok)
        row.addWidget(self.btn_no)
        row.addStretch(1)

        # Trash overlay (arriba a la derecha)
        self.btn_trash = QToolButton(self)
        self.btn_trash.setObjectName("ToolbarBtn")
        self.btn_trash.setText("🗑")
        self.btn_trash.setFixedSize(28, 28)
        self.btn_trash.clicked.connect(
            lambda: self.discardClicked.emit(self.sug_id))
        self.btn_trash.raise_()

        root.addWidget(self.lbl_img)
        root.addLayout(row)

    def _load_thumb(self):
        if self.thumb_path:
            pm = QPixmap(self.thumb_path)
        else:
            # placeholder simple
            pm = QPixmap(TILE, TILE)
            pm.fill(Qt.gray)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.lightGray)
            r = pm.rect().adjusted(24, 24, -24, -24)
            p.drawEllipse(r)
            p.end()
        # ajustar a cuadrado (cover)
        if not pm.isNull():
            pm = pm.scaled(
                TILE, TILE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.lbl_img.setPixmap(pm)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # posicionar trash overlay en esquina superior derecha del thumb
        x = self.width() - TILE_MARGIN - self.btn_trash.width()
        y = TILE_MARGIN
        self.btn_trash.move(x, y)


class PersonDetailView(QWidget):
    """
    Contenido del detalle de una persona/mascota.
    Header local (dentro del detalle):
      [Avatar redondo]  Título
      [Botones tipo link: Todos | Sugerencias (N)]

    Páginas:
      - page_all: placeholder por ahora
      - page_sugs: grilla de SuggestionTile con ✔ ✖ 🗑
    """
    requestBack = Signal()
    suggestionCountChanged = Signal(int)

    def __init__(self, cluster: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.cluster = cluster
        self._sugs: List[Dict[str, Any]] = list(cluster.get("suggestions", []))

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ───────── Header local ─────────
        hdr = QVBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        # Avatar circular
        self.lbl_avatar = QLabel(self)
        self.lbl_avatar.setFixedSize(40, 40)
        self._set_avatar(cluster.get("cover"))

        self.lbl_title = QLabel(cluster.get("title") or "Sin nombre", self)
        self.lbl_title.setObjectName("SectionTitle")

        top.addWidget(self.lbl_avatar)
        top.addWidget(self.lbl_title, 1)

        # Link buttons: Todos / Sugerencias
        links = QHBoxLayout()
        links.setContentsMargins(0, 0, 0, 0)
        links.setSpacing(12)

        self.btn_all = QToolButton(self)
        self.btn_all.setObjectName("ToolbarBtn")
        self.btn_all.setText("Todos")
        self.btn_all.clicked.connect(self.show_all)

        self.btn_sugs = QToolButton(self)
        self.btn_sugs.setObjectName("ToolbarBtn")
        self.btn_sugs.clicked.connect(self.show_suggestions)

        links.addWidget(self.btn_all)
        links.addWidget(self.btn_sugs)
        links.addStretch(1)

        hdr.addLayout(top)
        hdr.addLayout(links)
        root.addLayout(hdr)

        # ───────── Contenido ─────────
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 1)

        # Página ALL (placeholder de momento)
        self.page_all = QWidget(self)
        la = QVBoxLayout(self.page_all)
        la.setContentsMargins(0, 0, 0, 0)
        la.setSpacing(8)
        ph = QLabel(
            "Aquí iría la grilla de fotos/videos del cluster (pendiente).", self.page_all)
        ph.setObjectName("SectionText")
        la.addWidget(ph, 1, alignment=Qt.AlignTop)
        self.stack.addWidget(self.page_all)

        # Página SUGS
        self.page_sugs = QWidget(self)
        ls = QVBoxLayout(self.page_sugs)
        ls.setContentsMargins(0, 0, 0, 0)
        ls.setSpacing(0)

        self.scroll = QScrollArea(self.page_sugs)
        self.scroll.setWidgetResizable(True)
        # <- FIX: usar QFrame.NoFrame
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_host = QWidget(self.scroll)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)

        self.scroll.setWidget(self.grid_host)
        ls.addWidget(self.scroll, 1)
        self.stack.addWidget(self.page_sugs)

        # Estado inicial
        self._refresh_suggestions()
        self.show_suggestions()  # arrancamos mostrando sugerencias

    # ───────── Header helpers ─────────
    def _set_avatar(self, cover_path: Optional[str]):
        # redondo de 40x40 con cover o placeholder
        size = 40
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(QRect(0, 0, size, size))
        painter.setClipPath(path)

        if cover_path:
            src = QPixmap(cover_path)
            if not src.isNull():
                src = src.scaled(
                    size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap(0, 0, src)
            else:
                painter.fillRect(0, 0, size, size, Qt.gray)
        else:
            painter.fillRect(0, 0, size, size, Qt.gray)

        painter.end()
        self.lbl_avatar.setPixmap(pm)

    def _update_sug_link_text(self):
        n = len(self._sugs)
        self.btn_sugs.setText(f"Sugerencias ({n})")
        self.suggestionCountChanged.emit(n)

    # ───────── Páginas ─────────
    def show_all(self):
        self.stack.setCurrentWidget(self.page_all)
        self.btn_all.setEnabled(False)
        self.btn_sugs.setEnabled(True)

    def show_suggestions(self):
        self.stack.setCurrentWidget(self.page_sugs)
        self.btn_all.setEnabled(True)
        self.btn_sugs.setEnabled(False)

    # ───────── Sugerencias ─────────
    def _refresh_suggestions(self):
        # limpiar grilla
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # poblar
        cols = max(1, self.width() // (TILE + 2*TILE_MARGIN + 12))
        if cols < 1:
            cols = 1

        for i, sug in enumerate(self._sugs):
            tile = SuggestionTile(sug_id=str(
                sug["id"]), thumb_path=sug.get("thumb"))
            tile.acceptClicked.connect(self._on_accept)
            tile.rejectClicked.connect(self._on_reject)
            tile.discardClicked.connect(self._on_discard)
            r = i // cols
            c = i % cols
            self.grid.addWidget(tile, r, c)

        self._update_sug_link_text()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # relayout al cambiar ancho
        if self.stack.currentWidget() is self.page_sugs:
            self._refresh_suggestions()

    def _remove_sug_by_id(self, sug_id: str):
        self._sugs = [s for s in self._sugs if str(s.get("id")) != str(sug_id)]
        self._refresh_suggestions()

    def _on_accept(self, sug_id: str):
        # TODO: mover a “miembros confirmados” del cluster y persistir en DB
        self._remove_sug_by_id(sug_id)

    def _on_reject(self, sug_id: str):
        # TODO: marcar como “no es esta persona/mascota” para no sugerir de nuevo
        self._remove_sug_by_id(sug_id)

    def _on_discard(self, sug_id: str):
        # TODO: registrar como falso positivo (no es una cara válida; descartar muestra)
        self._remove_sug_by_id(sug_id)
