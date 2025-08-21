# src/picople/app/views/ThumbDelegate.py
from __future__ import annotations
from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtGui import QPainter, QFontMetrics, QIcon, QPixmap, QColor, QPainterPath
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget, QStyle

# Deben coincidir con MediaListModel
ROLE_KIND = Qt.UserRole + 1
ROLE_FAVORITE = Qt.UserRole + 2


class ThumbDelegate(QStyledItemDelegate):
    def __init__(self, tile: int = 160, text_lines: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
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

        # Selección
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

        # Pixmap principal
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

        # Overlays
        kind = index.data(ROLE_KIND)
        is_fav = bool(index.data(ROLE_FAVORITE) or False)

        # ▶ overlay (solo videos)
        if kind == "video":
            painter.setRenderHint(QPainter.Antialiasing, True)
            r_play = 14
            cx = icon_rect.right() - r_play - 6
            cy = icon_rect.bottom() - r_play - 6
            painter.save()
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(cx, cy), r_play, r_play)

            tri = QPainterPath()
            tri.moveTo(cx - 4, cy - 6)
            tri.lineTo(cx - 4, cy + 6)
            tri.lineTo(cx + 6, cy)
            tri.closeSubpath()
            painter.setBrush(QColor(255, 255, 255))
            painter.drawPath(tri)
            painter.restore()

        # ♥ overlay (solo si es favorito)
        if is_fav:
            painter.setRenderHint(QPainter.Antialiasing, True)
            r_heart = 10
            cx = icon_rect.right() - r_heart - 6
            cy = icon_rect.top() + r_heart + 6
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 140))
            painter.drawEllipse(QPoint(cx, cy), r_heart + 4, r_heart + 4)

            painter.setBrush(QColor(255, 80, 100))
            heart = QPainterPath()
            heart.moveTo(cx, cy + 3)
            heart.cubicTo(cx + 10, cy - 6, cx + 6, cy - 14, cx, cy - 6)
            heart.cubicTo(cx - 6, cy - 14, cx - 10, cy - 6, cx, cy + 3)
            painter.drawPath(heart)
            painter.restore()

        # Texto (si se desea)
        if self.text_lines > 0:
            txt = str(index.data(Qt.DisplayRole) or "")
            color = option.palette.highlightedText().color() if (option.state & QStyle.State_Selected) \
                else option.palette.text().color()
            painter.setPen(color)
            fm: QFontMetrics = option.fontMetrics
            line = fm.elidedText(txt, Qt.ElideMiddle, text_rect.width())
            painter.drawText(text_rect, Qt.AlignHCenter |
                             Qt.AlignVCenter, line)

        painter.restore()
