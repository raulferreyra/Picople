from __future__ import annotations
from typing import List
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QToolBar, QToolButton, QLabel,
    QStatusBar, QSlider
)
from PySide6.QtGui import QKeySequence, QShortcut, QFont

from .ImageView import ImageView
from .VideoView import VideoView
from picople.app.controllers import MediaNavigator, MediaItem


class MediaViewerPanel(QWidget):
    requestClose = Signal()

    def __init__(self, items: List[MediaItem], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.nav = MediaNavigator(items, start_index)
        self._seeking = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ────────────── Toolbar ──────────────
        self.tb = QToolBar()
        self.tb.setObjectName("ViewerToolbar")
        self.tb.setMovable(False)

        # Helpers para guardar las QAction
        def add_btn(text: str) -> tuple[QToolButton, object]:
            b = QToolButton()
            b.setText(text)
            b.setObjectName("ToolbarBtn")
            act = self.tb.addWidget(b)
            return b, act

        def add_sep() -> object:
            return self.tb.addSeparator()

        # Controles GENERALES (siempre visibles)
        self.btn_prev, self.act_prev = add_btn("◀")
        self.btn_next, self.act_next = add_btn("▶")
        self.btn_fav, self.act_fav = add_btn("♡")
        self.btn_close, self.act_close = add_btn("✕")

        # corazón con tipografía que tiene ♥/♡
        self.btn_fav.setCheckable(True)
        self.btn_fav.setFont(
            QFont("Segoe UI Symbol", self.btn_fav.font().pointSize()))
        self.btn_fav.toggled.connect(
            lambda on: self.btn_fav.setText("♥" if on else "♡"))

        # Separador entre GENERALES e IMAGEN
        self.sep_general_end = add_sep()

        # Controles de IMAGEN (grupo IMAGEN)
        self.btn_fit,      self.act_fit = add_btn("Ajustar")
        self.btn_100,      self.act_100 = add_btn("100%")
        self.btn_zoom_in,  self.act_zin = add_btn("+")
        self.btn_zoom_out, self.act_zout = add_btn("−")
        self.btn_rotate,   self.act_rot = add_btn("↻")

        # Separador entre IMAGEN y VIDEO
        self.sep_before_video = add_sep()

        # Controles de VIDEO (grupo VIDEO)
        self.btn_playpause, self.act_playpause = add_btn("⏯")
        self.sep_mid_video = add_sep()

        self.pos_slider = QSlider(Qt.Horizontal)
        self.pos_slider.setObjectName("MediaSlider")
        self.pos_slider.setRange(0, 0)
        self.pos_slider.setFixedWidth(260)
        self.act_pos = self.tb.addWidget(self.pos_slider)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setObjectName("StatusTag")
        self.act_time = self.tb.addWidget(self.lbl_time)

        self.sep_right_video = add_sep()

        self.btn_mute, self.act_mute = add_btn("🔊")
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setObjectName("MediaSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(120)
        self.act_vol = self.tb.addWidget(self.vol_slider)

        root.addWidget(self.tb)

        # ────────────── Contenido ──────────────
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

        # ────────────── Status ──────────────
        self.status = QStatusBar()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setObjectName("StatusLabel")
        self.status.addWidget(self.lbl_status, 1)
        root.addWidget(self.status)

        # ────────────── Conexiones ──────────────
        # Generales
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_close.clicked.connect(lambda: self.requestClose.emit())

        # Imagen
        self.btn_fit.clicked.connect(lambda: self._image_action("fit"))
        self.btn_100.clicked.connect(lambda: self._image_action("100"))
        self.btn_zoom_in.clicked.connect(lambda: self._image_action("zin"))
        self.btn_zoom_out.clicked.connect(lambda: self._image_action("zout"))
        self.btn_rotate.clicked.connect(lambda: self._image_action("rot"))

        # Video (una vez creadas vistas)
        self.btn_playpause.clicked.connect(self._play_pause)
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

        # Grupos (listas de QAction) para conmutar visibilidad por tipo
        self._img_actions = [
            self.sep_general_end,
            self.act_fit, self.act_100, self.act_zin, self.act_zout, self.act_rot,
            self.sep_before_video,
        ]
        self._vid_actions = [
            self.act_playpause, self.sep_mid_video,
            self.act_pos, self.act_time,
            self.sep_right_video, self.act_mute, self.act_vol,
        ]

        # Estado inicial: ocultamos ambos grupos, luego cargamos y mostramos el que toca
        self._set_group_visible(self._img_actions, False)
        self._set_group_visible(self._vid_actions, False)

        self._load_current()

    # ────────────── Helpers ──────────────
    def _mk_shortcut(self, seq: str, fn):
        sc = QShortcut(QKeySequence(seq), self)
        sc.activated.connect(fn)
        return sc

    def _set_group_visible(self, actions: list, on: bool):
        for act in actions:
            act.setVisible(on)

    def _fmt_time(self, ms: int) -> str:
        s = max(0, ms // 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

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
            # Solo IMAGEN
            self._set_group_visible(self._vid_actions, False)
            self._set_group_visible(self._img_actions, True)
        else:
            self.video_view.load_path(it.path)
            self.stack.setCurrentIndex(1)
            # Solo VIDEO
            self._set_group_visible(self._img_actions, False)
            self._set_group_visible(self._vid_actions, True)

        self.btn_prev.setEnabled(self.nav.has_prev())
        self.btn_next.setEnabled(self.nav.has_next())

    # ────────────── Navegación ──────────────
    def _prev(self):
        if self.nav.prev():
            self._load_current()

    def _next(self):
        if self.nav.next():
            self._load_current()

    # ────────────── Acciones imagen ──────────────
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

    # ────────────── Acciones video ──────────────
    def _play_pause(self):
        if self.stack.currentIndex() == 1:
            self.video_view.play_pause()

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
