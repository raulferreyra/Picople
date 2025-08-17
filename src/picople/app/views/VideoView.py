from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider, QHBoxLayout
from PySide6.QtGui import QAction

# QtMultimedia puede faltar en algunos sistemas; lo manejamos con fallback
try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAS_QTMEDIA = True
except Exception:
    HAS_QTMEDIA = False


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        if not HAS_QTMEDIA:
            self._label = QLabel(
                "Backend de video no disponible.\nInstala codecs/QtMultimedia.")
            self._label.setAlignment(Qt.AlignCenter)
            lay.addWidget(self._label, 1)
            self._player = None
            return

        self._video = QVideoWidget()
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setVideoOutput(self._video)
        self._player.setAudioOutput(self._audio)

        # barra básica
        bar = QHBoxLayout()
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 1000)
        bar.addWidget(self._slider)

        lay.addWidget(self._video, 1)
        lay.addLayout(bar)

        self._player.durationChanged.connect(self._on_duration)
        self._player.positionChanged.connect(self._on_position)
        self._slider.sliderMoved.connect(self._on_seek)

    def load_path(self, path: str) -> bool:
        if not HAS_QTMEDIA or self._player is None:
            return False
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.pause()
        return True

    def play_pause(self):
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def set_volume(self, vol: int):
        if self._player and self._player.audioOutput():
            self._player.audioOutput().setVolume(max(0.0, min(1.0, vol / 100.0)))

    def is_ready(self) -> bool:
        return self._player is not None

    # slots
    def _on_duration(self, ms: int):
        self._slider.setEnabled(ms > 0)

    def _on_position(self, ms: int):
        dur = max(1, self._player.duration())
        self._slider.blockSignals(True)
        self._slider.setValue(int(ms / dur * 1000))
        self._slider.blockSignals(False)

    def _on_seek(self, x: int):
        dur = self._player.duration()
        self._player.setPosition(int(dur * (x / 1000.0)))
