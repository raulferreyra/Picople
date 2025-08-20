# src/picople/app/views/MediaViewerPanel.py
from __future__ import annotations
from typing import List, Optional
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QToolBar, QToolButton, QLabel, QStatusBar, QSlider
)
from PySide6.QtGui import QKeySequence, QShortcut, QFont

from .ImageView import ImageView
from .VideoView import VideoView
from picople.app.controllers import MediaNavigator, MediaItem
from picople.infrastructure.db import Database


class MediaViewerPanel(QWidget):
    requestClose = Signal()
    favoriteChanged = Signal(str, bool)  # path, state

    def __init__(self, items: List[MediaItem], start_index: int = 0, db: Optional[Database] = None, parent=None):
        super().__init__(parent)
        self.nav = MediaNavigator(items, start_index)
        self.db = db
        self._seeking = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
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

        self.btn_playpause = QToolButton()
        self.btn_playpause.setText("⏯")

        self.btn_fav = QToolButton()
        self.btn_fav.setFont(
            QFont("Segoe UI Symbol", self.btn_fav.font().pointSize()))
        self.btn_fav.setText("♡")
        self.btn_fav.setCheckable(True)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")

        for b in (self.btn_prev, self.btn_next, self.btn_fit, self.btn_100,
                  self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate,
                  self.btn_fav, self.btn_close):
            b.setObjectName("ToolbarBtn")
            self.tb.addWidget(b)

        # Play/Pause (solo videos)
        self.tb.addSeparator()
        self.btn_playpause.setObjectName("ToolbarBtn")
        self.act_playpause = self.tb.addWidget(self.btn_playpause)
        self.act_playpause.setVisible(False)

        # Controles de video
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

        self.tb.addSeparator()
        self.tb.addWidget(self.pos_slider)
        self.tb.addWidget(self.lbl_time)
        self.tb.addSeparator()
        self.tb.addWidget(self.btn_mute)
        self.tb.addWidget(self.vol_slider)

        root.addWidget(self.tb)

        # Contenido
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
        self.stack.addWidget(page_img)
        self.stack.addWidget(page_vid)
        root.addWidget(self.stack, 1)

        # Status
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
        self.btn_fav.toggled.connect(self._toggle_fav)
        self.btn_close.clicked.connect(lambda: self.requestClose.emit())

        self._mk_shortcut("Left", self._prev)
        self._mk_shortcut("Right", self._next)
        self._mk_shortcut("Space", self._play_pause)
        self._mk_shortcut("Ctrl+0", lambda: self._image_action("fit"))
        self._mk_shortcut("Ctrl+1", lambda: self._image_action("100"))
        self._mk_shortcut("Ctrl++", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+=", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+-", lambda: self._image_action("zout"))
        self._mk_shortcut("R", lambda: self._image_action("rot"))

        # señales de video
        self.video_view.positionChanged.connect(self._on_video_pos)
        self.video_view.durationChanged.connect(self._on_video_dur)
        self.video_view.mutedChanged.connect(
            lambda m: self.btn_mute.setText("🔇" if m else "🔊"))
        self.video_view.volumeChanged.connect(
            lambda v: self.vol_slider.setValue(v))
        self.video_view.playingChanged.connect(
            lambda playing: self.btn_playpause.setText("⏸" if playing else "⏯"))
        self.pos_slider.sliderMoved.connect(
            lambda v: self.video_view.set_position(v))
        self.pos_slider.sliderPressed.connect(
            lambda: setattr(self, "_seeking", True))
        self.pos_slider.sliderReleased.connect(self._seek_release)
        self.btn_mute.clicked.connect(self.video_view.toggle_mute)
        self.vol_slider.valueChanged.connect(self.video_view.set_volume)

        self._load_current()

    # helpers
    def _mk_shortcut(self, seq: str, fn):
        sc = QShortcut(QKeySequence(seq), self)
        sc.activated.connect(fn)
        return sc

    def _fmt_time(self, ms: int) -> str:
        s = max(0, ms // 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    # carga elemento actual
    def _load_current(self):
        it = self.nav.current()
        if not it:
            self.lbl_status.setText("Sin elementos")
            return
        name = Path(it.path).name
        self.lbl_status.setText(
            f"{self.nav.index+1}/{self.nav.count()}  •  {name}")

        # estado ♥ desde DB (si está)
        if self.db and self.db.is_open:
            self.btn_fav.blockSignals(True)
            self.btn_fav.setChecked(self.db.is_favorite(it.path))
            self.btn_fav.setText("♥" if self.btn_fav.isChecked() else "♡")
            self.btn_fav.blockSignals(False)

        if it.kind == "image":
            self.video_view.stop()
            self.image_view.load_path(it.path)
            self.stack.setCurrentIndex(0)
            # muestra controles de imagen
            for b in (self.btn_fit, self.btn_100, self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate):
                b.setVisible(True)
            # oculta controles de video
            self.act_playpause.setVisible(False)
            self.btn_playpause.setVisible(False)
            self.pos_slider.setVisible(False)
            self.lbl_time.setVisible(False)
            self.btn_mute.setVisible(False)
            self.vol_slider.setVisible(False)
        else:
            self.video_view.load_path(it.path)
            self.stack.setCurrentIndex(1)
            # oculta controles de imagen
            for b in (self.btn_fit, self.btn_100, self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate):
                b.setVisible(False)
            # muestra controles de video
            self.act_playpause.setVisible(True)
            self.btn_playpause.setVisible(True)
            self.pos_slider.setVisible(True)
            self.lbl_time.setVisible(True)
            self.btn_mute.setVisible(True)
            self.vol_slider.setVisible(True)

        self.btn_prev.setEnabled(self.nav.has_prev())
        self.btn_next.setEnabled(self.nav.has_next())

    # navegación
    def _prev(self):
        if self.nav.prev():
            self._load_current()

    def _next(self):
        if self.nav.next():
            self._load_current()

    # imagen
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

    # video
    def _play_pause(self):
        if self.stack.currentIndex() == 1:
            self.video_view.play_pause()

    # favorito
    def _toggle_fav(self, checked: bool):
        self.btn_fav.setText("♥" if checked else "♡")
        it = self.nav.current()
        if it and self.db and self.db.is_open:
            self.db.set_favorite(it.path, checked)
            self.favoriteChanged.emit(it.path, checked)

    # video status
    def _on_video_pos(self, pos_ms: int):
        if not self._seeking:
            self.pos_slider.setValue(pos_ms)
        dur = self.pos_slider.maximum()
        self.lbl_time.setText(
            f"{self._fmt_time(pos_ms)} / {self._fmt_time(dur)}")

    def _on_video_dur(self, dur_ms: int):
        self.pos_slider.setRange(0, max(0, dur_ms))
        self.lbl_time.setText(f"00:00 / {self._fmt_time(dur_ms)}")

    def _seek_release(self):
        self._seeking = False
        self.video_view.set_position(self.pos_slider.value())
