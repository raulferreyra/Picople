from __future__ import annotations
from typing import List
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QToolBar, QToolButton, QLabel, QStatusBar
from PySide6.QtGui import QKeySequence

from .ImageView import ImageView
from .VideoView import VideoView
from picople.app.controllers import MediaNavigator, MediaItem


class MediaViewerPanel(QWidget):
    def __init__(self, items: List[MediaItem], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.nav = MediaNavigator(items, start_index)
        self._fullscreen = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

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
        for b in (self.btn_prev, self.btn_next, self.btn_fit, self.btn_100, self.btn_zoom_in, self.btn_zoom_out, self.btn_rotate, self.btn_playpause):
            self.tb.addWidget(b)
        root.addWidget(self.tb)

        self.stack = QStackedWidget()
        self.image_view = ImageView()
        self.video_view = VideoView()
        from PySide6.QtWidgets import QVBoxLayout, QWidget
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

        self.status = QStatusBar()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setObjectName("StatusLabel")
        self.status.addWidget(self.lbl_status, 1)
        root.addWidget(self.status)

        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_fit.clicked.connect(lambda: self._image_action("fit"))
        self.btn_100.clicked.connect(lambda: self._image_action("100"))
        self.btn_zoom_in.clicked.connect(lambda: self._image_action("zin"))
        self.btn_zoom_out.clicked.connect(lambda: self._image_action("zout"))
        self.btn_rotate.clicked.connect(lambda: self._image_action("rot"))
        self.btn_playpause.clicked.connect(self._play_pause)

        self._mk_shortcut("Left", self._prev)
        self._mk_shortcut("Right", self._next)
        self._mk_shortcut("Space", self._play_pause)
        self._mk_shortcut("Ctrl+0", lambda: self._image_action("fit"))
        self._mk_shortcut("Ctrl+1", lambda: self._image_action("100"))
        self._mk_shortcut("Ctrl++", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+=", lambda: self._image_action("zin"))
        self._mk_shortcut("Ctrl+-", lambda: self._image_action("zout"))
        self._mk_shortcut("R", lambda: self._image_action("rot"))
        self._mk_shortcut("Esc", lambda: self.parent().hide()
                          if self.parent() else None)

        self._load_current()

    def _mk_shortcut(self, seq: str, fn):
        from PySide6.QtWidgets import QToolButton
        btn = QToolButton(self)
        btn.setShortcut(QKeySequence(seq))
        btn.clicked.connect(fn)
        btn.setVisible(False)

    def _load_current(self):
        it = self.nav.current()
        if not it:
            self.lbl_status.setText("Sin elementos")
            return
        name = Path(it.path).name
        self.lbl_status.setText(
            f"{self.nav.index+1}/{self.nav.count()}  •  {name}")

        if it.kind == "image":
            self.image_view.load_path(it.path)
            self.stack.setCurrentIndex(0)
            self.btn_playpause.setEnabled(False)
        else:
            self.video_view.load_path(it.path)
            self.stack.setCurrentIndex(1)
            self.btn_playpause.setEnabled(self.video_view.is_ready())

        self.btn_prev.setEnabled(self.nav.has_prev())
        self.btn_next.setEnabled(self.nav.has_next())

    def _prev(self):
        if self.nav.prev():
            self._load_current()

    def _next(self):
        if self.nav.next():
            self._load_current()

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

    def _play_pause(self):
        if self.stack.currentIndex() == 1:
            self.video_view.play_pause()
