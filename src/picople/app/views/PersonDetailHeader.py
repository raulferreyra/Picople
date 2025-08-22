from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QToolButton, QStyle
)


class PersonDetailHeader(QWidget):
    """
    Header compacto para el detalle de persona/mascota:
    [←]  (avatar redondo)  Nombre del cluster           [✎]
          └── (clic en “Sugerencias”) opcional abajo en el contenedor
    """
    requestBack = Signal()
    requestRename = Signal()

    def __init__(self, *, title: str, cover: Optional[str] = None, kind: str = "person", parent=None):
        super().__init__(parent)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # ← Volver
        self.btn_back = QToolButton(self)
        self.btn_back.setObjectName("ToolbarBtn")
        self.btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_back.clicked.connect(self.requestBack.emit)

        # Avatar circular
        self.avatar_lbl = QLabel(self)
        self.avatar_lbl.setFixedSize(QSize(56, 56))
        self.avatar_lbl.setPixmap(self._make_round_avatar(56, cover, kind))
        self.avatar_lbl.setScaledContents(True)

        # Título
        self.title_lbl = QLabel(title, self)
        # heredamos estilos del tema (mismo objectName que headers de sección)
        self.title_lbl.setObjectName("SectionTitle")
        self.title_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # ✎ Renombrar
        self.btn_rename = QToolButton(self)
        self.btn_rename.setObjectName("ToolbarBtn")
        self.btn_rename.setText("✎")
        self.btn_rename.setToolTip("Renombrar")
        self.btn_rename.clicked.connect(self.requestRename.emit)

        lay.addWidget(self.btn_back)
        lay.addWidget(self.avatar_lbl)
        lay.addWidget(self.title_lbl, 1)
        lay.addWidget(self.btn_rename)

    # ───────────────── helpers ─────────────────
    def set_title(self, text: str) -> None:
        self.title_lbl.setText(text)

    def set_avatar(self, cover: Optional[str], kind: str = "person") -> None:
        self.avatar_lbl.setPixmap(self._make_round_avatar(56, cover, kind))

    def _make_round_avatar(self, size_px: int, cover: Optional[str], kind: str) -> QPixmap:
        size = QSize(size_px, size_px)
        pm = QPixmap(size)
        pm.fill(Qt.transparent)

        # base: imagen si existe; si no, usamos icono del sistema para placeholder
        if cover:
            src = QPixmap(cover)
            if not src.isNull():
                src = src.scaled(
                    size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                # recorte centrado cuadrado
                x = (src.width() - size.width()) // 2
                y = (src.height() - size.height()) // 2
                src = src.copy(x, y, size.width(), size.height())
            else:
                src = self._placeholder_icon(size_px, kind)
        else:
            src = self._placeholder_icon(size_px, kind)

        # máscara circular
        mask = QPixmap(size)
        mask.fill(Qt.transparent)
        painter = QPainter(mask)
        painter.setRenderHints(QPainter.Antialiasing |
                               QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addEllipse(0, 0, size.width(), size.height())
        painter.fillPath(path, Qt.white)
        painter.end()

        # pintar con clip circular
        painter = QPainter(pm)
        painter.setRenderHints(QPainter.Antialiasing |
                               QPainter.SmoothPixmapTransform)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, src)
        painter.end()

        # borde sutil
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        pen_col = self.palette().windowText().color()
        pen_col.setAlpha(60)
        painter.setPen(pen_col)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(0, 0, size.width()-1, size.height()-1)
        painter.end()

        return pm

    def _placeholder_icon(self, size_px: int, kind: str) -> QPixmap:
        # persona por defecto; si es "pet" usa otro estándar
        sp = QStyle.SP_DirIcon if kind == "person" else QStyle.SP_DriveDVDIcon
        icon_pm = self.style().standardIcon(sp).pixmap(
            int(size_px*0.9), int(size_px*0.9))
        # centrar sobre fondo acorde al tema
        base = QPixmap(size_px, size_px)
        base.fill(Qt.transparent)
        painter = QPainter(base)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = self.palette().window().color()
        bg = bg.lighter(105) if bg.value() < 128 else bg.darker(105)
        painter.fillRect(0, 0, size_px, size_px, bg)

        x = (size_px - icon_pm.width()) // 2
        y = (size_px - icon_pm.height()) // 2
        painter.drawPixmap(x, y, icon_pm)
        painter.end()
        return base
