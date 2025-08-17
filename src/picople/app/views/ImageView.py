from __future__ import annotations
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QScrollArea, QLabel

from PIL import Image, ImageOps

# Si tienes pillow-heif instalado, PIL ya sabrá abrir HEIC/HEIF.
# Para GIF animado, tomamos el primer frame.


def _pil_to_qimage(pil_img: Image.Image) -> QImage:
    # Normaliza a RGB(A) y calcula stride (bytesPerLine)
    if pil_img.mode == "RGBA":
        data = pil_img.tobytes("raw", "RGBA")
        bpl = pil_img.width * 4
        qimg = QImage(data, pil_img.width, pil_img.height,
                      bpl, QImage.Format_RGBA8888)
    elif pil_img.mode == "RGB":
        data = pil_img.tobytes("raw", "RGB")
        bpl = pil_img.width * 3
        qimg = QImage(data, pil_img.width, pil_img.height,
                      bpl, QImage.Format_RGB888)
    else:
        pil_img = pil_img.convert("RGBA")
        data = pil_img.tobytes("raw", "RGBA")
        bpl = pil_img.width * 4
        qimg = QImage(data, pil_img.width, pil_img.height,
                      bpl, QImage.Format_RGBA8888)
    return qimg.copy()


class ImageView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self.setWidget(self._label)

        self._orig: Optional[QImage] = None
        self._zoom = 1.0
        self._fit = True
        self._rotation = 0
        # pan con arrastre
        self._panning = False
        self._pan_start = QPoint(0, 0)
        self._h0 = 0
        self._v0 = 0

    def load_path(self, path: str) -> bool:
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            # primer frame si animado
            try:
                img.seek(0)
            except Exception:
                pass
            self._orig = _pil_to_qimage(img)
            self._zoom = 1.0
            self._rotation = 0
            self._render()
            return True
        except Exception:
            self._orig = None
            self._label.setPixmap(QPixmap())
            self._label.setText("No se pudo abrir la imagen.")
            return False

    def set_fit_to_window(self, fit: bool) -> None:
        self._fit = fit
        self._render()

    def zoom_reset(self) -> None:
        self._zoom = 1.0
        self._fit = False
        self._render()

    def zoom_in(self, step: float = 0.1) -> None:
        self._fit = False
        self._zoom = min(6.0, self._zoom + step)
        self._render()

    def zoom_out(self, step: float = 0.1) -> None:
        self._fit = False
        self._zoom = max(0.1, self._zoom - step)
        self._render()

    def rotate_90(self) -> None:
        self._rotation = (self._rotation + 90) % 360
        self._render()

    def current_zoom_percent(self) -> int:
        if self._fit:
            return 100  # conceptual, se ajusta a ventana
        return int(self._zoom * 100)

    def _render(self) -> None:
        if self._orig is None:
            return
        img = self._orig

        # rotación con QTransform y stride correcto
        if self._rotation:
            from PySide6.QtGui import QTransform
            tr = QTransform()
            tr.rotate(self._rotation)
            img = img.transformed(tr, Qt.SmoothTransformation)

        pm = QPixmap.fromImage(img)
        if self._fit:
            avail = self.viewport().size()
            if not pm.isNull():
                pm = pm.scaled(avail.width(), avail.height(),
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            if self._zoom != 1.0 and not pm.isNull():
                w = int(pm.width() * self._zoom)
                h = int(pm.height() * self._zoom)
                pm = pm.scaled(w, h, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)

        self._label.setPixmap(pm)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._fit:
            self._render()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            delta = e.angleDelta().y()
            if delta > 0:
                self.zoom_in(0.1)
            else:
                self.zoom_out(0.1)
            e.accept()
        else:
            super().wheelEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self._fit and self._label.pixmap() and not self._label.pixmap().isNull():
            self._panning = True
            self._pan_start = e.pos()
            self._h0 = self.horizontalScrollBar().value()
            self._v0 = self.verticalScrollBar().value()
            self.setCursor(Qt.ClosedHandCursor)
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._panning:
            dx = e.pos().x() - self._pan_start.x()
            dy = e.pos().y() - self._pan_start.y()
            self.horizontalScrollBar().setValue(self._h0 - dx)
            self.verticalScrollBar().setValue(self._v0 - dy)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._panning and e.button() == Qt.LeftButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            e.accept()
        else:
            super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        # doble clic: alterna ajustar/100%
        if self._fit:
            self.zoom_reset()
        else:
            self.set_fit_to_window(True)
        e.accept()

    @staticmethod
    def _rot_matrix(deg: int):
        from PySide6.QtGui import QTransform
        tr = QTransform()
        tr.rotate(deg)
        return tr
