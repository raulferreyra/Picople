# src/picople/app/views/MediaViewerPanel.py
from __future__ import annotations
from typing import List, Optional
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QToolBar, QToolButton, QLabel, QStatusBar,
    QSlider
)

from picople.app.controllers import MediaNavigator, MediaItem
from picople.infrastructure.db import Database
from .ImageView import ImageView
from .VideoView import VideoView


class MediaViewerPanel(QWidget):
    requestClose = Signal()
    favoriteToggled = Signal(str, bool)   # path, fav

    def __init__(self, items: List[MediaItem], start_index: int = 0, *, db: Optional[Database] = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.nav = MediaNavigator(items, start_index)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ───── Toolbar
        self.tb = QToolBar()
        self.tb.setObjectName("ViewerToolbar")
        self.tb.setMovable(False)

        self.btn_prev = QToolButton()
        self.btn_prev.setText("◀")
        self.btn_next = QToolButton()
        self.btn_next.setText("▶")

        # Controles de IMAGEN
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

        # Controles de VIDEO
        self.btn_playpause = QToolButton()
        self.btn_playpause.setText("⏯")
        self.pos_slider = QSlider(Qt.Horizontal)
        self.pos_slider.setObjectName("MediaSlider")
        self.pos_slider.setRange(0, 0)
        self.pos_slider.setFixedWidth(260)
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setObjectName("StatusTag")
        self.btn_mute = QToolButton()
        self.btn_mute.setObjectName("ToolbarBtn")
        self.btn_mute.setText("🔊")
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setObjectName("MediaSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(120)

        self.btn_fav = QToolButton()
        self.btn_fav.setFont(
            QFont("Segoe UI Symbol", self.btn_fav.font().pointSize()))
        self.btn_fav.setText("♡")
        self.btn_fav.setCheckable(True)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")

        # Añadir en orden: generales → imagen → video → favoritos/cerrar
        for b in (self.btn_prev, self.btn_next):
            b.setObjectName("ToolbarBtn")
            self.tb.addWidget(b)

        # grupo imagen
        self.tb.addSeparator()
        for b in (self.btn_fit, self.btn_100, self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate):
            b.setObjectName("ToolbarBtn")
            self.tb.addWidget(b)
        self.sep_img = self.tb.addSeparator()

        # grupo video
        self.tb.addSeparator()
        self.tb.addWidget(self.btn_playpause)
        self.tb.addWidget(self.pos_slider)
        self.tb.addWidget(self.lbl_time)
        self.tb.addWidget(self.btn_mute)
        self.tb.addWidget(self.vol_slider)
        self.sep_vid = self.tb.addSeparator()

        # fav/cerrar
        self.tb.addWidget(self.btn_fav)
        self.tb.addWidget(self.btn_close)

        root.addWidget(self.tb)

        # ───── Contenido
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

        self.stack.addWidget(page_img)  # 0
        self.stack.addWidget(page_vid)  # 1
        root.addWidget(self.stack, 1)

        # ───── Status
        self.status = QStatusBar()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setObjectName("StatusLabel")
        self.status.addWidget(self.lbl_status, 1)
        root.addWidget(self.status)

        # ───── Conexiones
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_fit.clicked.connect(lambda: self._image_action("fit"))
        self.btn_100.clicked.connect(lambda: self._image_action("100"))
        self.btn_zoom_in.clicked.connect(lambda: self._image_action("zin"))
        self.btn_zoom_out.clicked.connect(lambda: self._image_action("zout"))
        self.btn_rotate.clicked.connect(lambda: self._image_action("rot"))

        self.btn_playpause.clicked.connect(self._play_pause)
        self.btn_mute.clicked.connect(self.video_view.toggle_mute)
        self.vol_slider.valueChanged.connect(self.video_view.set_volume)

        self.pos_slider.sliderMoved.connect(self.video_view.set_position)
        self.video_view.positionChanged.connect(self._on_video_pos)
        self.video_view.durationChanged.connect(self._on_video_dur)
        self.video_view.mutedChanged.connect(
            lambda m: self.btn_mute.setText("🔇" if m else "🔊"))
        self.video_view.playingChanged.connect(
            lambda p: self.btn_playpause.setText("⏸" if p else "⏯"))

        self.btn_fav.toggled.connect(self._toggle_fav)
        self.btn_close.clicked.connect(lambda: self.requestClose.emit())

        # Atajos
        self._mk_shortcut("Left", self._prev)
        self._mk_shortcut("Right", self._next)
        self._mk_shortcut("Space", self._play_pause)
        self._mk_shortcut("Ctrl+0", lambda: self._image_action("fit"))
        self._mk_shortcut("Ctrl+1", lambda: self._image_action("100"))
        self._mk_shortcut("Ctrl++", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+=", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+-", lambda: self._image_action("zout"))
        self._mk_shortcut("R", lambda: self._image_action("rot"))

        self._seeking = False
        self._set_mode("image")  # default, se corrige en _load_current
        self._load_current()

    # Helpers
    def _mk_shortcut(self, seq: str, fn):
        sc = QShortcut(QKeySequence(seq), self)
        sc.activated.connect(fn)
        return sc

    def _set_mode(self, mode: str):  # "image" | "video"
        img_widgets = [self.btn_fit, self.btn_100, self.btn_zoom_in,
                       self.btn_zoom_out, self.btn_rotate, self.sep_img]
        vid_widgets = [self.btn_playpause, self.pos_slider,
                       self.lbl_time, self.btn_mute, self.vol_slider, self.sep_vid]
        is_img = (mode == "image")
        for w in img_widgets:
            w.setVisible(is_img)
        for w in vid_widgets:
            w.setVisible(not is_img)

    def _fmt_time(self, ms: int) -> str:
        s = max(0, ms // 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    # Carga
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
            self._set_mode("image")
        else:
            self.video_view.load_path(it.path)
            self.stack.setCurrentIndex(1)
            self._set_mode("video")

        self.btn_prev.setEnabled(self.nav.has_prev())
        self.btn_next.setEnabled(self.nav.has_next())
        self.btn_fav.setChecked(bool(getattr(it, "favorite", False)))

    # Navegación
    def _prev(self):
        if self.nav.prev():
            self._load_current()

    def _next(self):
        if self.nav.next():
            self._load_current()

    # Imagen
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

    # Video
    def _play_pause(self):
        if self.stack.currentIndex() == 1:
            self.video_view.play_pause()

    def _on_video_pos(self, pos_ms: int):
        self.pos_slider.blockSignals(True)
        self.pos_slider.setValue(pos_ms)
        self.pos_slider.blockSignals(False)
        dur = self.pos_slider.maximum()
        self.lbl_time.setText(
            f"{self._fmt_time(pos_ms)} / {self._fmt_time(dur)}")

    def _on_video_dur(self, dur_ms: int):
        self.pos_slider.setRange(0, max(0, dur_ms))
        self.lbl_time.setText(f"00:00 / {self._fmt_time(dur_ms)}")

    # Favoritos
    def _toggle_fav(self, checked: bool):
        it = self.nav.current()
        if not it:
            return
        it.favorite = bool(checked)
        self.btn_fav.setText("♥" if checked else "♡")
        if self.db:
            try:
                self.db.set_favorite(it.path, checked)
            except Exception:
                pass
        self.favoriteToggled.emit(it.path, checked)
