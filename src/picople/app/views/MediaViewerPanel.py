from __future__ import annotations
from typing import List
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QToolBar, QToolButton, QLabel,
    QStatusBar, QSlider
)

from picople.app.controllers import MediaNavigator, MediaItem
from picople.app.views.ImageView import ImageView
from picople.app.views.VideoView import VideoView


class MediaViewerPanel(QWidget):
    requestClose = Signal()

    def __init__(self, items: List[MediaItem], start_index: int = 0, db=None, parent=None):
        super().__init__(parent)
        self.nav = MediaNavigator(items, start_index)
        self.db = db
        self._seeking = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ───────── toolbar ─────────
        self.tb = QToolBar()
        self.tb.setObjectName("ViewerToolbar")
        self.tb.setMovable(False)

        # grupo: navegación
        self.btn_prev = QToolButton(text="◀")
        self._add_btn(self.btn_prev)
        self.btn_next = QToolButton(text="▶")
        self._add_btn(self.btn_next)

        # grupo: imagen
        self.sep_img = self.tb.addSeparator()
        self.btn_fit = QToolButton(text="Ajustar")
        self._add_btn(self.btn_fit)
        self.btn_100 = QToolButton(text="100%")
        self._add_btn(self.btn_100)
        self.btn_zoom_in = QToolButton(text="+")
        self._add_btn(self.btn_zoom_in)
        self.btn_zoom_out = QToolButton(text="−")
        self._add_btn(self.btn_zoom_out)
        self.btn_rotate = QToolButton(text="↻")
        self._add_btn(self.btn_rotate)

        # grupo: video
        self.sep_vid = self.tb.addSeparator()
        self.btn_playpause = QToolButton(text="⏯")
        self._add_btn(self.btn_playpause)
        self.pos_slider = QSlider(Qt.Horizontal)
        self.pos_slider.setObjectName("MediaSlider")
        self.pos_slider.setRange(0, 0)
        self.pos_slider.setFixedWidth(260)
        self.tb.addWidget(self.pos_slider)
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setObjectName("StatusTag")
        self.tb.addWidget(self.lbl_time)
        self.btn_mute = QToolButton(text="🔊")
        self._add_btn(self.btn_mute)
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setObjectName("MediaSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(120)
        self.tb.addWidget(self.vol_slider)

        # grupo: misc (fav / cerrar) — al final
        self.tb.addSeparator()
        self.btn_fav = QToolButton()
        self._add_btn(self.btn_fav)
        self.btn_fav.setFont(
            QFont("Segoe UI Symbol", self.btn_fav.font().pointSize()))
        self.btn_fav.setCheckable(True)
        self.btn_fav.setText("♡")
        self.btn_close = QToolButton(text="✕")
        self._add_btn(self.btn_close)

        root.addWidget(self.tb)

        # ───────── contenido ─────────
        self.stack = QStackedWidget()
        self.image_view = ImageView()
        self.video_view = VideoView()
        self.stack.addWidget(self._wrap(self.image_view))  # idx 0
        self.stack.addWidget(self._wrap(self.video_view))  # idx 1
        root.addWidget(self.stack, 1)

        # ───────── status ─────────
        self.status = QStatusBar()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setObjectName("StatusLabel")
        self.status.addWidget(self.lbl_status, 1)
        root.addWidget(self.status)

        # conexiones
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_fit.clicked.connect(lambda: self._img("fit"))
        self.btn_100.clicked.connect(lambda: self._img("100"))
        self.btn_zoom_in.clicked.connect(lambda: self._img("zin"))
        self.btn_zoom_out.clicked.connect(lambda: self._img("zout"))
        self.btn_rotate.clicked.connect(lambda: self._img("rot"))
        self.btn_playpause.clicked.connect(self._play_pause)
        self.btn_mute.clicked.connect(self.video_view.toggle_mute)
        self.vol_slider.valueChanged.connect(self.video_view.set_volume)
        self.btn_fav.toggled.connect(self._toggle_fav)
        self.btn_close.clicked.connect(lambda: self.requestClose.emit())

        self.video_view.positionChanged.connect(self._on_pos)
        self.video_view.durationChanged.connect(self._on_dur)
        self.video_view.mutedChanged.connect(
            lambda m: self.btn_mute.setText("🔇" if m else "🔊"))
        self.video_view.playingChanged.connect(
            lambda p: self.btn_playpause.setText("⏸" if p else "⏯"))

        self.pos_slider.sliderPressed.connect(
            lambda: setattr(self, "_seeking", True))
        self.pos_slider.sliderReleased.connect(self._seek_end)
        self.pos_slider.sliderMoved.connect(self.video_view.set_position)

        # atajos
        self._sc("Left", self._prev)
        self._sc("Right", self._next)
        self._sc("Space", self._play_pause)
        self._sc("Ctrl+0", lambda: self._img("fit"))
        self._sc("Ctrl+1", lambda: self._img("100"))
        self._sc("Ctrl++", lambda: self._img("zin"))
        self._sc("Ctrl+=", lambda: self._img("zin"))
        self._sc("Ctrl+-", lambda: self._img("zout"))
        self._sc("R", lambda: self._img("rot"))

        self._load_current()

    # helpers ui
    def _add_btn(self, b: QToolButton): b.setObjectName(
        "ToolbarBtn"); self.tb.addWidget(b)

    def _wrap(self, w): from PySide6.QtWidgets import QWidget, QVBoxLayout; p = QWidget(
    ); l = QVBoxLayout(p); l.setContentsMargins(0, 0, 0, 0); l.addWidget(w); return p

    def _sc(self, s, fn): sc = QShortcut(
        QKeySequence(s), self); sc.activated.connect(fn)

    # modos
    def _show_image_controls(self, on: bool):
        for b in (self.btn_fit, self.btn_100, self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate):
            b.setVisible(on)
        self.sep_img.setVisible(on)

    def _show_video_controls(self, on: bool):
        for w in (self.btn_playpause, self.pos_slider, self.lbl_time, self.btn_mute, self.vol_slider):
            w.setVisible(on)
        self.sep_vid.setVisible(on)

    # carga item
    def _load_current(self):
        it = self.nav.current()
        if not it:
            self.lbl_status.setText("Sin elementos")
            return

        name = Path(it.path).name
        self.lbl_status.setText(
            f"{self.nav.index+1}/{self.nav.count()}  •  {name}")
        self.btn_fav.blockSignals(True)
        self.btn_fav.setChecked(getattr(it, "favorite", False))
        self.btn_fav.setText("♥" if self.btn_fav.isChecked() else "♡")
        self.btn_fav.blockSignals(False)

        if it.kind == "image":
            self.video_view.stop()
            self.image_view.load_path(it.path)
            self.stack.setCurrentIndex(0)
            self._show_image_controls(True)
            self._show_video_controls(False)
        else:
            self.video_view.load_path(it.path)
            self.stack.setCurrentIndex(1)
            self._show_image_controls(False)
            self._show_video_controls(True)

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
    def _img(self, what: str):
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

    def _fmt(self, ms: int) -> str:
        s = max(0, ms//1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _on_pos(self, ms: int):
        if not self._seeking:
            self.pos_slider.setValue(ms)
        self.lbl_time.setText(
            f"{self._fmt(ms)} / {self._fmt(self.pos_slider.maximum())}")

    def _on_dur(self, ms: int):
        self.pos_slider.setRange(0, max(0, ms))
        self.lbl_time.setText(f"00:00 / {self._fmt(ms)}")

    def _seek_end(self):
        self._seeking = False
        self.video_view.set_position(self.pos_slider.value())

    # favorito
    def _toggle_fav(self, on: bool):
        it = self.nav.current()
        self.btn_fav.setText("♥" if on else "♡")
        setattr(it, "favorite", on)
        if self.db:
            try:
                self.db.set_favorite(it.path, on)
            except Exception:
                pass
