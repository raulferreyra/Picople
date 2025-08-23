# app/views/SuggestionTile.py
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolButton


TILE = 160
TILE_MARGIN = 8
TILE_BTN_H = 28


class SuggestionTile(QWidget):
    """
    Tarjeta de sugerencia con: imagen, ✔, ✖, ⭐ y 🗑 (falso positivo).
    Señales: acceptClicked(id), rejectClicked(id), coverClicked(id), discardClicked(id)
    """
    from PySide6.QtCore import Signal
    acceptClicked = Signal(str)
    rejectClicked = Signal(str)
    coverClicked = Signal(str)
    discardClicked = Signal(str)

    def __init__(self, sug_id: str, thumb_path: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.sug_id = sug_id
        self.thumb_path = thumb_path

        self.setFixedSize(TILE + 2*TILE_MARGIN, TILE +
                          TILE_BTN_H + 2*TILE_MARGIN)

        root = QVBoxLayout(self)
        root.setContentsMargins(TILE_MARGIN, TILE_MARGIN,
                                TILE_MARGIN, TILE_MARGIN)
        root.setSpacing(6)

        self.lbl_img = QLabel(self)
        self.lbl_img.setFixedSize(TILE, TILE)
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self._load_thumb()

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(6)

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

        self.btn_star = QToolButton(self)
        self.btn_star.setObjectName("ToolbarBtn")
        self.btn_star.setText("⭐")
        self.btn_star.setToolTip("Usar como portada")
        self.btn_star.clicked.connect(
            lambda: self.coverClicked.emit(self.sug_id))

        bar.addWidget(self.btn_ok)
        bar.addWidget(self.btn_no)
        bar.addWidget(self.btn_star)
        bar.addStretch(1)

        self.btn_trash = QToolButton(self)
        self.btn_trash.setObjectName("ToolbarBtn")
        self.btn_trash.setText("🗑")
        self.btn_trash.setFixedSize(28, 28)
        self.btn_trash.setToolTip("Descartar (falso positivo)")
        self.btn_trash.clicked.connect(
            lambda: self.discardClicked.emit(self.sug_id))
        self.btn_trash.raise_()

        root.addWidget(self.lbl_img)
        root.addLayout(bar)

    def _load_thumb(self):
        if self.thumb_path:
            pm = QPixmap(self.thumb_path)
        else:
            pm = QPixmap(TILE, TILE)
            pm.fill(Qt.gray)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.lightGray)
            r = pm.rect().adjusted(24, 24, -24, -24)
            p.drawEllipse(r)
            p.end()
        if not pm.isNull():
            pm = pm.scaled(
                TILE, TILE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.lbl_img.setPixmap(pm)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        x = self.width() - TILE_MARGIN - self.btn_trash.width()
        y = TILE_MARGIN
        self.btn_trash.move(x, y)
