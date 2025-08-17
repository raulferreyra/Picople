from __future__ import annotations
from typing import List, Optional
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QStackedWidget, QToolBar, QToolButton,
    QLabel, QStatusBar, QWidget, QMessageBox
)

from .ImageView import ImageView
from .VideoView import VideoView
from picople.app.controllers import MediaNavigator, MediaItem


class MediaViewer(QDialog):
    """
    Visor interno: imágenes y videos, con navegación anterior/siguiente,
    zoom (100% / ajustar), rotación, fullscreen y atajos.
    """

    def __init__(self, items: List[MediaItem], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visor • Picople")
        self.resize(1000, 700)
        self.setModal(True)

        self.nav = MediaNavigator(items, start_index)
        self._fullscreen = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        self.tb = QToolBar()
        self.tb.setObjectName("MainToolbar")
        self.tb.setMovable(False)

        self.btn_prev = QToolButton()
        self.btn_prev.setText("◀")
        self.btn_next = QToolButton()
        self.btn_next.setText("▶")
        self.btn_fit = QToolButton()
        self.btn_fit.setText("Ajustar")
        self.btn_100 = QToolButton()
        self.btn_100.setText("100%")
        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("+")
        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("−")
        self.btn_rotate = QToolButton()
        self.btn_rotate.setText("↻")
        self.btn_playpause = QToolButton()
        self.btn_playpause.setText("⏯")
        self.btn_fullscreen = QToolButton()
        self.btn_fullscreen.setText("⛶")

        for b in (self.btn_prev, self.btn_next, self.btn_fit, self.btn_100,
                  self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate,
                  self.btn_playpause, self.btn_fullscreen):
            self.tb.addWidget(b)

        root.addWidget(self.tb)

        # Stack central
        self.stack = QStackedWidget()
        self.image_view = ImageView()
        self.video_view = VideoView()

        self.page_image = QWidget()
        layi = QVBoxLayout(self.page_image)
        layi.setContentsMargins(0, 0, 0, 0)
        layi.addWidget(self.image_view)
        self.page_video = QWidget()
        layv = QVBoxLayout(self.page_video)
        layv.setContentsMargins(0, 0, 0, 0)
        layv.addWidget(self.video_view)

        self.stack.addWidget(self.page_image)  # idx 0
        self.stack.addWidget(self.page_video)  # idx 1

        root.addWidget(self.stack, 1)

        # Status bar
        self.status = QStatusBar()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setObjectName("StatusLabel")
        self.status.addWidget(self.lbl_status, 1)
        root.addWidget(self.status)

        # Conexiones
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_fit.clicked.connect(lambda: self._image_action("fit"))
        self.btn_100.clicked.connect(lambda: self._image_action("100"))
        self.btn_zoom_in.clicked.connect(lambda: self._image_action("zin"))
        self.btn_zoom_out.clicked.connect(lambda: self._image_action("zout"))
        self.btn_rotate.clicked.connect(lambda: self._image_action("rot"))
        self.btn_playpause.clicked.connect(self._play_pause)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)

        # Atajos
        self._mk_shortcut("Left", self._prev)
        self._mk_shortcut("Right", self._next)
        self._mk_shortcut("Space", self._play_pause)
        self._mk_shortcut("F", self._toggle_fullscreen)
        self._mk_shortcut("Ctrl+0", lambda: self._image_action("fit"))
        self._mk_shortcut("Ctrl+1", lambda: self._image_action("100"))
        self._mk_shortcut("Ctrl++", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+=", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+-", lambda: self._image_action("zout"))
        self._mk_shortcut("R", lambda: self._image_action("rot"))
        self._mk_shortcut("Esc", self.reject)

        self._load_current()

    def _mk_shortcut(self, seq: str, fn):
        sc = QKeySequence(seq)
        btn = QToolButton(self)  # objeto dummy para el atajo
        btn.setShortcut(sc)
        btn.clicked.connect(fn)
        btn.setVisible(False)

    # ---------- Carga/Navegación ----------
    def _load_current(self):
        item = self.nav.current()
        if not item:
            self.lbl_status.setText("Sin elementos")
            return
        p = item.path
        name = Path(p).name
        self.setWindowTitle(f"{name} — Visor • Picople")
        self.lbl_status.setText(
            f"{self.nav.index+1}/{self.nav.count()}  •  {name}")

        if item.kind == "image":
            ok = self.image_view.load_path(p)
            self.stack.setCurrentIndex(0)
            self.btn_playpause.setEnabled(False)
        else:
            ok = self.video_view.load_path(p)
            self.stack.setCurrentIndex(1)
            self.btn_playpause.setEnabled(self.video_view.is_ready())

        if not ok:
            QMessageBox.information(self, "Visor", f"No se pudo abrir: {p}")

        # estado de navegación
        self.btn_prev.setEnabled(self.nav.has_prev())
        self.btn_next.setEnabled(self.nav.has_next())

    def _prev(self):
        if self.nav.prev():
            self._load_current()

    def _next(self):
        if self.nav.next():
            self._load_current()

    # ---------- Acciones imagen ----------
    def _image_action(self, what: str):
        if self.stack.currentIndex() != 0:
            return
        if what == "fit":
            self.image_view.set_fit_to_window(True)
        elif what == "100":
            self.image_view.zoom_reset()
        elif what == "zin":
            self.image_view.zoom_in()
        elif what == "zout":
            self.image_view.zoom_out()
        elif what == "rot":
            self.image_view.rotate_90()
        # feedback
        self.lbl_status.setText(
            f"{self.nav.index+1}/{self.nav.count()}  •  zoom {self.image_view.current_zoom_percent()}%")

    # ---------- Acciones video ----------
    def _play_pause(self):
        if self.stack.currentIndex() == 1:
            self.video_view.play_pause()

    # ---------- Fullscreen ----------
    def _toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
