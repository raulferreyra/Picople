from __future__ import annotations
from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtGui import QPainter, QFontMetrics, QIcon, QPixmap, QColor, QPainterPath
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget, QStyle

ROLE_KIND = Qt.UserRole + 1
ROLE_FAVORITE = Qt.UserRole + 2


class ThumbDelegate(QStyledItemDelegate):
    def __init__(self, tile: int = 160, text_lines: int = 2, parent: QWidget | None = None):
        super().__init__(parent)
        self.tile = int(tile)
        self.text_lines = max(0, int(text_lines))  # 0 = sin texto
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

        # Selección
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Área interior + rects
        r = option.rect.adjusted(self.hpad, self.vpad, -self.hpad, -self.vpad)
        icon_rect = QRect(r.left(), r.top(), r.width(), self.tile)
        text_rect = QRect(
            r.left(),
            r.top() + self.tile + (self.text_pad_top if self.text_lines > 0 else 0),
            r.width(),
            r.height() - self.tile - (self.text_pad_top if self.text_lines > 0 else 0),
        )

        # Pixmap del ícono/miniatura
        deco = index.data(Qt.DecorationRole)
        pm: QPixmap | None = None
        if isinstance(deco, QIcon):
            pm = deco.pixmap(self.tile, self.tile)
        elif isinstance(deco, QPixmap):
            pm = deco

        if pm and not pm.isNull():
            pm2 = pm.scaled(self.tile, self.tile,
                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = icon_rect.left() + (icon_rect.width() - pm2.width()) // 2
            y = icon_rect.top() + (icon_rect.height() - pm2.height()) // 2
            painter.drawPixmap(x, y, pm2)

        # Badge de vídeo (después de tener icon_rect)
        kind = index.data(ROLE_KIND)
        if kind == "video":
            painter.setRenderHint(QPainter.Antialiasing, True)
            rbadge = 14
            cx = icon_rect.right() - rbadge - 6
            cy = icon_rect.bottom() - rbadge - 6

            painter.save()
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(cx, cy), rbadge, rbadge)

            path = QPainterPath()
            tri = [QPoint(cx - 4, cy - 6), QPoint(cx -
                                                  4, cy + 6), QPoint(cx + 6, cy)]
            path.moveTo(tri[0])
            path.lineTo(tri[1])
            path.lineTo(tri[2])
            path.closeSubpath()
            painter.setBrush(QColor(255, 255, 255))
            painter.drawPath(path)
            painter.restore()

        # Overlay "favorito" en esquina superior derecha
        fav = bool(index.data(ROLE_FAVORITE))
        if fav:
            painter.save()
            r = 12
            cx = icon_rect.right() - r - 6
            cy = icon_rect.top() + r + 6
            painter.setRenderHint(QPainter.Antialiasing, True)
            # círculo oscuro
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(cx, cy), r, r)
            # corazón
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(240, 70, 90))
            path = QPainterPath()
            path.moveTo(cx, cy+4)
            path.cubicTo(cx-10, cy-6, cx-6, cy-10, cx, cy-2)
            path.cubicTo(cx+6, cy-10, cx+10, cy-6, cx, cy+4)
            painter.drawPath(path)
            painter.restore()

        # Texto (opcional)
        if self.text_lines > 0:
            txt = str(index.data(Qt.DisplayRole) or "")
            color = option.palette.highlightedText().color() if (
                option.state & QStyle.State_Selected) else option.palette.text().color()
            painter.setPen(color)

            fm: QFontMetrics = option.fontMetrics
            pathlike = ("/" in txt) or ("\\" in txt)
            if pathlike:
                norm = txt.replace("\\", "/")
                name = norm.rsplit("/", 1)[-1]
                parent = norm.rsplit(
                    "/", 2)[-2] if norm.count("/") >= 1 else ""
                if parent:
                    parent = f"…/{parent}"
            else:
                name, parent = txt, ""

            line1 = fm.elidedText(name, Qt.ElideMiddle, text_rect.width())
            y = text_rect.top()
            painter.drawText(QRect(text_rect.left(), y, text_rect.width(), fm.height()),
                             Qt.AlignHCenter | Qt.AlignVCenter, line1)
            if self.text_lines > 1 and parent:
                line2 = fm.elidedText(
                    parent, Qt.ElideMiddle, text_rect.width())
                y += fm.height()
                painter.drawText(QRect(text_rect.left(), y, text_rect.width(), fm.height()),
                                 Qt.AlignHCenter | Qt.AlignVCenter, line2)

        painter.restore()
