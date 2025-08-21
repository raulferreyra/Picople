# src/picople/app/views/MediaViewerPanel.py
from __future__ import annotations
from typing import List, Optional
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QToolBar, QToolButton,
    QLabel, QStatusBar, QSlider
)
from PySide6.QtGui import QKeySequence, QShortcut, QFont

from picople.infrastructure.db import Database
from picople.app.controllers import MediaNavigator, MediaItem
from .ImageView import ImageView
from .VideoView import VideoView


class MediaViewerPanel(QWidget):
    requestClose = Signal()
    favoriteToggled = Signal(str, bool)   # (path, is_fav)

    def __init__(
        self,
        items: List[MediaItem],
        start_index: int = 0,
        *,
        db: Optional[Database] = None,
        parent=None
    ):
        super().__init__(parent)
        self.nav = MediaNavigator(items, start_index)
        self.db: Optional[Database] = db
        self._seeking = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ───────────────── Toolbar ─────────────────
        # Usa los mismos objectName que tu QSS ya estiló
        self.tb = QToolBar()
        self.tb.setObjectName("MainToolbar")
        self.tb.setMovable(False)

        # Botones generales
        self.btn_prev = QToolButton()
        self._style_btn(self.btn_prev,  "◀")
        self.btn_next = QToolButton()
        self._style_btn(self.btn_next,  "▶")
        self.btn_fav = QToolButton()
        self._style_btn(self.btn_fav,   "♡")
        self.btn_close = QToolButton()
        self._style_btn(self.btn_close, "✕")

        self.btn_fav.setCheckable(True)
        # Garantiza que ♥/♡ existan en la fuente
        self.btn_fav.setFont(
            QFont("Segoe UI Symbol", self.btn_fav.font().pointSize()))

        self.act_prev = self.tb.addWidget(self.btn_prev)
        self.act_next = self.tb.addWidget(self.btn_next)
        self.act_fav = self.tb.addWidget(self.btn_fav)
        self.act_close = self.tb.addWidget(self.btn_close)

        # Controles de IMAGEN (un único separador controlado)
        self.sep_img = self.tb.addSeparator()
        self.btn_fit = QToolButton()
        self._style_btn(self.btn_fit,      "Ajustar")
        self.btn_100 = QToolButton()
        self._style_btn(self.btn_100,      "100%")
        self.btn_zoom_in = QToolButton()
        self._style_btn(self.btn_zoom_in,  "+")
        self.btn_zoom_out = QToolButton()
        self._style_btn(self.btn_zoom_out, "−")
        self.btn_rotate = QToolButton()
        self._style_btn(self.btn_rotate,   "↻")

        self.act_fit = self.tb.addWidget(self.btn_fit)
        self.act_100 = self.tb.addWidget(self.btn_100)
        self.act_zin = self.tb.addWidget(self.btn_zoom_in)
        self.act_zout = self.tb.addWidget(self.btn_zoom_out)
        self.act_rotate = self.tb.addWidget(self.btn_rotate)

        self._img_actions = [
            self.sep_img, self.act_fit, self.act_100,
            self.act_zin, self.act_zout, self.act_rotate
        ]

        # Controles de VIDEO (un único separador controlado)
        self.sep_vid = self.tb.addSeparator()
        self.btn_playpause = QToolButton()
        self._style_btn(self.btn_playpause, "⏯")

        self.pos_slider = QSlider(Qt.Horizontal)
        self.pos_slider.setObjectName("MediaSlider")
        self.pos_slider.setRange(0, 0)
        self.pos_slider.setFixedWidth(260)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setObjectName("StatusTag")

        self.btn_mute = QToolButton()
        self._style_btn(self.btn_mute, "🔊")

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setObjectName("MediaSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(120)

        self.act_play = self.tb.addWidget(self.btn_playpause)
        self.act_pos = self.tb.addWidget(self.pos_slider)
        self.act_time = self.tb.addWidget(self.lbl_time)
        self.act_mute = self.tb.addWidget(self.btn_mute)
        self.act_vol = self.tb.addWidget(self.vol_slider)

        self._vid_actions = [
            self.sep_vid, self.act_play, self.act_pos,
            self.act_time, self.act_mute, self.act_vol
        ]

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

        self.stack.addWidget(page_img)  # 0 = imagen
        self.stack.addWidget(page_vid)  # 1 = video
        root.addWidget(self.stack, 1)

        # ───────────────── Status ─────────────────
        self.status = QStatusBar()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setObjectName("StatusLabel")
        self.status.addWidget(self.lbl_status, 1)
        root.addWidget(self.status)

        # ───────────────── Conexiones ─────────────────
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

        # Video
        self.btn_playpause.clicked.connect(self._play_pause)
        self.pos_slider.sliderMoved.connect(
            lambda v: self.video_view.set_position(v))
        self.pos_slider.sliderPressed.connect(self._seek_press)
        self.pos_slider.sliderReleased.connect(self._seek_release)
        self.btn_mute.clicked.connect(self._toggle_mute)
        self.vol_slider.valueChanged.connect(self._set_volume)

        # Señales del reproductor → UI
        self.video_view.positionChanged.connect(self._on_video_pos)
        self.video_view.durationChanged.connect(self._on_video_dur)
        self.video_view.mutedChanged.connect(
            lambda m: self.btn_mute.setText("🔇" if m else "🔊"))
        self.video_view.volumeChanged.connect(self.vol_slider.setValue)
        self.video_view.playingChanged.connect(
            lambda play: self.btn_playpause.setText("⏸" if play else "⏯"))

        # Favoritos (no mutamos MediaItem; persistimos y notificamos)
        self.btn_fav.toggled.connect(self._toggle_fav)

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

        # Carga inicial
        self._load_current()

    # ───────────────── Helpers ─────────────────
    def _style_btn(self, btn: QToolButton, text: str) -> None:
        btn.setText(text)
        btn.setObjectName("ToolbarBtn")

    def _mk_shortcut(self, seq: str, fn):
        sc = QShortcut(QKeySequence(seq), self)
        sc.activated.connect(fn)
        return sc

    def _fmt_time(self, ms: int) -> str:
        s = max(0, ms // 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _show_actions(self, actions: list, visible: bool) -> None:
        for a in actions:
            a.setVisible(visible)

    def _apply_mode(self, kind: str) -> None:
        if kind == "image":
            self._show_actions(self._img_actions, True)
            self._show_actions(self._vid_actions, False)
        else:
            self._show_actions(self._img_actions, False)
            self._show_actions(self._vid_actions, True)

    # ───────────────── Carga y navegación ─────────────────
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
            self._apply_mode("image")
        else:
            self.video_view.load_path(it.path)
            self.stack.setCurrentIndex(1)
            self._apply_mode("video")

        # sync favorito desde DB si existe; si no, usar el flag de MediaItem
        fav = None
        try:
            if self.db and self.db.is_open:
                fav = self.db.is_favorite(it.path)
        except Exception:
            fav = None
        if fav is None:
            fav = it.favorite

        self.btn_fav.blockSignals(True)
        self.btn_fav.setChecked(bool(fav))
        self.btn_fav.setText("♥" if fav else "♡")
        self.btn_fav.blockSignals(False)

        self.btn_prev.setEnabled(self.nav.has_prev())
        self.btn_next.setEnabled(self.nav.has_next())

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

    def _seek_press(self):
        self._seeking = True

    def _seek_release(self):
        self._seeking = False
        self.video_view.set_position(self.pos_slider.value())

    def _toggle_mute(self):
        self.video_view.toggle_mute()

    def _set_volume(self, v: int):
        self.video_view.set_volume(v)

    def _on_video_pos(self, pos_ms: int):
        if not self._seeking:
            self.pos_slider.setValue(pos_ms)
        dur = self.pos_slider.maximum()
        self.lbl_time.setText(
            f"{self._fmt_time(pos_ms)} / {self._fmt_time(dur)}")

    def _on_video_dur(self, dur_ms: int):
        self.pos_slider.setRange(0, max(0, dur_ms))
        self.lbl_time.setText(f"00:00 / {self._fmt_time(dur_ms)}")

    # ───────────────── Favoritos ─────────────────
    def _toggle_fav(self, checked: bool):
        it = self.nav.current()
        if not it:
            return
        # Persistimos en DB y reflejamos UI; NO mutamos MediaItem (es frozen).
        ok = True
        try:
            if self.db and self.db.is_open:
                self.db.set_favorite(it.path, bool(checked))
        except Exception:
            ok = False

        if not ok:
            # Revertir visual si falló la DB
            self.btn_fav.blockSignals(True)
            self.btn_fav.setChecked(not checked)
            self.btn_fav.setText("♥" if not checked else "♡")
            self.btn_fav.blockSignals(False)
            return

        # UI inmediata
        self.btn_fav.setText("♥" if checked else "♡")
        # Notificar a la grilla para actualizar overlay sin recargar
        self.favoriteToggled.emit(it.path, bool(checked))
