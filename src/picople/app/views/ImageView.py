from __future__ import annotations
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QScrollArea, QLabel

from PIL import Image

# Si tienes pillow-heif instalado, PIL ya sabrá abrir HEIC/HEIF.
# Para GIF animado, tomamos el primer frame.


def _pil_to_qimage(pil_img: Image.Image) -> QImage:
    if pil_img.mode not in ("RGB", "RGBA"):
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", pil_img.mode)
    if pil_img.mode == "RGBA":
        qimg = QImage(data, pil_img.width, pil_img.height,
                      QImage.Format_RGBA8888)
    else:  # RGB
        qimg = QImage(data, pil_img.width, pil_img.height,
                      QImage.Format_RGB888)
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
        self._rotation = 0  # grados 0/90/180/270

    def load_path(self, path: str) -> bool:
        try:
            img = Image.open(path)
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

        # rotación
        if self._rotation:
            transform = QImage(img)
            if self._rotation == 90:
                img = transform.transformed(self._rot_matrix(90))
            elif self._rotation == 180:
                img = transform.transformed(self._rot_matrix(180))
            elif self._rotation == 270:
                img = transform.transformed(self._rot_matrix(270))

        pm = QPixmap.fromImage(img)
        if self._fit:
            # escalar a viewport manteniendo aspecto
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

    @staticmethod
    def _rot_matrix(deg: int):
        from PySide6.QtGui import QTransform
        tr = QTransform()
        tr.rotate(deg)
        return tr
