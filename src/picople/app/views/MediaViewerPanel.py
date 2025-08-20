from __future__ import annotations
from typing import List
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QToolBar, QToolButton, QLabel, QStatusBar
)
from PySide6.QtGui import QKeySequence, QShortcut, QFont

from .ImageView import ImageView
from .VideoView import VideoView
from picople.app.controllers import MediaNavigator, MediaItem
from picople.core.log import log


class MediaViewerPanel(QWidget):
    requestClose = Signal()

    def __init__(self, items: List[MediaItem], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.nav = MediaNavigator(items, start_index)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ───────────────── Toolbar ─────────────────
        self.tb = QToolBar()
        self.tb.setObjectName("ViewerToolbar")
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

        # Play/Pausa como botón separado (se añadirá como acción aparte)
        self.btn_playpause = QToolButton()
        self.btn_playpause.setText("⏯")

        self.btn_fav = QToolButton()
        self.btn_fav.setFont(
            QFont("Segoe UI Symbol", self.btn_fav.font().pointSize()))
        self.btn_fav.setText("♡")
        self.btn_fav.setCheckable(True)
        self.btn_fav.toggled.connect(
            lambda on: self.btn_fav.setText("♥" if on else "♡"))

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")

        # Botones "generales" (NO incluir play/pause aquí)
        for b in (
            self.btn_prev, self.btn_next, self.btn_fit, self.btn_100,
            self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate,
            self.btn_fav, self.btn_close
        ):
            b.setObjectName("ToolbarBtn")
            self.tb.addWidget(b)

        # Play/Pause como acción independiente para poder ocultar/mostrar
        self.btn_playpause.setObjectName("ToolbarBtn")
        self.tb.addSeparator()
        self.act_playpause = self.tb.addWidget(self.btn_playpause)
        self.act_playpause.setVisible(False)   # oculto por defecto

        root.addWidget(self.tb)

        # ───────────────── Contenido ─────────────────
        self.stack = QStackedWidget()

        self.image_view = ImageView()
        self.video_view = VideoView()

        page_img = QWidget()
        li = QVBoxLayout(page_img)
        li.setContentsMargins(0, 0, 0, 0)
        li.addWidget(self.image_view)

        page_vid = QWidget()
        lv = QVBoxLayout(page_vid)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self.video_view)

        self.stack.addWidget(page_img)  # index 0
        self.stack.addWidget(page_vid)  # index 1
        root.addWidget(self.stack, 1)

        # ───────────────── Status ─────────────────
        self.status = QStatusBar()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setObjectName("StatusLabel")
        self.status.addWidget(self.lbl_status, 1)
        root.addWidget(self.status)

        # ───────────────── Conexiones ─────────────────
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_fit.clicked.connect(lambda: self._image_action("fit"))
        self.btn_100.clicked.connect(lambda: self._image_action("100"))
        self.btn_zoom_in.clicked.connect(lambda: self._image_action("zin"))
        self.btn_zoom_out.clicked.connect(lambda: self._image_action("zout"))
        self.btn_rotate.clicked.connect(lambda: self._image_action("rot"))
        self.btn_playpause.clicked.connect(self._play_pause)
        self.btn_fav.toggled.connect(self._toggle_fav)
        self.btn_close.clicked.connect(lambda: self.requestClose.emit())

        # Atajos de teclado (nivel panel)
        self._mk_shortcut("Left", self._prev)
        self._mk_shortcut("Right", self._next)
        self._mk_shortcut("Space", self._play_pause)
        self._mk_shortcut("Ctrl+0", lambda: self._image_action("fit"))
        self._mk_shortcut("Ctrl+1", lambda: self._image_action("100"))
        self._mk_shortcut("Ctrl++", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+=", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+-", lambda: self._image_action("zout"))
        self._mk_shortcut("R", lambda: self._image_action("rot"))

        self._load_current()

    # ───────────────── Helpers ─────────────────
    def _mk_shortcut(self, seq: str, fn):
        sc = QShortcut(QKeySequence(seq), self)
        sc.activated.connect(fn)
        return sc

    def _load_current(self):
        it = self.nav.current()
        if not it:
            self.lbl_status.setText("Sin elementos")
            return

        name = Path(it.path).name
        self.lbl_status.setText(
            f"{self.nav.index+1}/{self.nav.count()}  •  {name}")

        if it.kind == "image":
            self.video_view.stop()
            self.image_view.load_path(it.path)
            self.stack.setCurrentIndex(0)
            # Oculta play/pause en imágenes (acción y widget, por robustez)
            self.act_playpause.setVisible(False)
            self.btn_playpause.setVisible(False)
        else:
            self.video_view.load_path(it.path)
            self.stack.setCurrentIndex(1)
            # Muestra play/pause en videos
            self.act_playpause.setVisible(True)
            self.btn_playpause.setVisible(True)

        self.btn_prev.setEnabled(self.nav.has_prev())
        self.btn_next.setEnabled(self.nav.has_next())

    # ───────────────── Navegación ─────────────────
    def _prev(self):
        if self.nav.prev():
            self._load_current()

    def _next(self):
        if self.nav.next():
            self._load_current()

    # ───────────────── Acciones imagen ─────────────────
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
        self.lbl_status.setText(
            f"{self.nav.index+1}/{self.nav.count()}  •  zoom {self.image_view.current_zoom_percent()}%")

    # ───────────────── Acciones video ─────────────────
    def _play_pause(self):
        if self.stack.currentIndex() == 1:
            self.video_view.play_pause()

    # ───────────────── Favoritos (UI) ─────────────────
    def _toggle_fav(self, checked: bool):
        # Solo UI: cambia el iconito (si tu fuente no tiene ♥/♡, cambia la fuente de este botón a "Segoe UI Symbol")
        self.btn_fav.setText("♥" if checked else "♡")
