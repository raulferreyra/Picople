from __future__ import annotations
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QFontMetrics, QIcon, QPixmap
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget, QStyle


class ThumbDelegate(QStyledItemDelegate):
    def __init__(self, tile: int = 160, text_lines: int = 2, parent: QWidget | None = None):
        super().__init__(parent)
        # permite 0 líneas para ocultar nombres
        self.tile = int(tile)
        self.text_lines = max(0, int(text_lines))
        self.vpad = 8
        self.hpad = 10
        self.text_pad_top = 6

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        fm = option.fontMetrics
        line_h = fm.height()
        text_h = (line_h * self.text_lines) if self.text_lines > 0 else 0
        pad_top = (self.text_pad_top if self.text_lines > 0 else 0)
        h = self.vpad + self.tile + pad_top + text_h + self.vpad
        w = self.hpad + self.tile + self.hpad
        return QSize(w, h)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()

        # Fondo selección (usar QStyle.State_Selected)
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Área interior
        r = option.rect.adjusted(self.hpad, self.vpad, -self.hpad, -self.vpad)
        icon_rect = QRect(r.left(), r.top(), r.width(), self.tile)
        text_rect = QRect(
            r.left(),
            r.top() + self.tile + (self.text_pad_top if self.text_lines > 0 else 0),
            r.width(),
            r.height() - self.tile - (self.text_pad_top if self.text_lines > 0 else 0),
        )

        # Icono / pixmap
        deco = index.data(Qt.DecorationRole)
        pm: QPixmap | None = None
        if isinstance(deco, QIcon):
            pm = deco.pixmap(self.tile, self.tile)
        elif isinstance(deco, QPixmap):
            pm = deco
        # dibujar icono centrado manteniendo aspecto
        if pm and not pm.isNull():
            pm2 = pm.scaled(self.tile, self.tile,
                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = icon_rect.left() + (icon_rect.width() - pm2.width()) // 2
            y = icon_rect.top() + (icon_rect.height() - pm2.height()) // 2
            painter.drawPixmap(x, y, pm2)

        # Texto (opcional)
        if self.text_lines > 0:
            txt = str(index.data(Qt.DisplayRole) or "")
            color = option.palette.highlightedText().color() if (
                option.state & QStyle.State_Selected) else option.palette.text().color()
            painter.setPen(color)

            fm: QFontMetrics = option.fontMetrics
            # Si parece ruta, separar nombre y carpeta; si no, solo nombre
            pathlike = ("/" in txt) or ("\\" in txt)
            if pathlike:
                norm = txt.replace("\\", "/")
