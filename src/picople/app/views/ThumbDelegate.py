from __future__ import annotations
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QFontMetrics, QIcon
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget


class ThumbDelegate(QStyledItemDelegate):
    def __init__(self, tile: int = 160, text_lines: int = 2, parent: QWidget | None = None):
        super().__init__(parent)
        self.tile = tile
        self.text_lines = max(1, text_lines)
        self.vpad = 8
        self.hpad = 10
        self.text_pad_top = 6

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        fm = option.fontMetrics
        line_h = fm.height()
        text_h = line_h * self.text_lines
        h = self.vpad + self.tile + self.text_pad_top + text_h + self.vpad
        w = self.hpad + self.tile + self.hpad
        return QSize(w, h)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()

        # Fondo selección
        if option.state & QStyleOptionViewItem.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Rectangulitos
        r = option.rect.adjusted(self.hpad, self.vpad, -self.hpad, -self.vpad)
        icon_rect = QRect(r.left(), r.top(), r.width(), self.tile)
        text_rect = QRect(r.left(), r.top() + self.tile + self.text_pad_top,
                          r.width(), r.height() - self.tile - self.text_pad_top)

        # Icono (mantener aspecto, centrado)
        icon: QIcon = index.data(Qt.DecorationRole)
        if icon:
            pm = icon.pixmap(self.tile, self.tile)
            if not pm.isNull():
                # escalar a caja manteniendo aspecto
                pm = pm.scaled(self.tile, self.tile,
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = icon_rect.left() + (icon_rect.width() - pm.width()) // 2
                y = icon_rect.top() + (icon_rect.height() - pm.height()) // 2
                painter.drawPixmap(x, y, pm)

        # Texto con elipsis (hasta N líneas)
        txt = str(index.data(Qt.DisplayRole) or "")
        color = option.palette.highlightedText().color(
        ) if option.state & QStyleOptionViewItem.State_Selected else option.palette.text().color()
        painter.setPen(color)

        fm: QFontMetrics = option.fontMetrics

        # Si parece ruta, partimos en nombre y carpeta; si no, usamos todo como nombre
        pathlike = ("/" in txt) or ("\\" in txt)
        if pathlike:
            norm = txt.replace("\\", "/")
            name = norm.rsplit("/", 1)[-1]
            parent = norm.rsplit("/", 2)[-2] if norm.count("/") >= 1 else ""
            # ejemplo de parent “…/Fotos” (último segmento)
            if parent:
                parent = f"…/{parent}"
        else:
            name = txt
            parent = ""

        line1 = fm.elidedText(name, Qt.ElideMiddle, text_rect.width())
        # Solo dibuja 2da línea si hay espacio configurado y hay algo que mostrar
        line2 = fm.elidedText(parent, Qt.ElideMiddle, text_rect.width()) if (
            self.text_lines > 1 and parent) else None

        # Dibujo centrado
        y = text_rect.top()
        painter.drawText(
            QRect(text_rect.left(), y, text_rect.width(), fm.height()),
            Qt.AlignHCenter | Qt.AlignVCenter,
            line1
        )
        if line2:
            y += fm.height()
            painter.drawText(
                QRect(text_rect.left(), y, text_rect.width(), fm.height()),
                Qt.AlignHCenter | Qt.AlignVCenter,
                line2
            )
