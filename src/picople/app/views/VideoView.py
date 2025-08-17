from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        lay.addWidget(self.video_widget)

        self.audio = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video_widget)
        self.player.setAudioOutput(self.audio)
        self._ready = False

        # señales para estado/errores
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(lambda e, s: self._on_error(e, s))

    def _on_status(self, st):
        # LoadedMedia / BufferedMedia son OK
        self._ready = st in (QMediaPlayer.LoadedMedia,
                             QMediaPlayer.BufferedMedia)

    def _on_error(self, err, strm):
        # ante error: parar y limpiar
        try:
            self.player.stop()
            self.player.setSource(QUrl())  # libera
        except Exception:
            pass
        self._ready = False

    def load_path(self, path: str) -> bool:
        try:
            # SIEMPRE parar y limpiar antes de nueva fuente
            self.player.stop()
            # importantísimo para evitar segfaults
            self.player.setSource(QUrl())
            self._ready = False

            url = QUrl.fromLocalFile(path)
            self.player.setSource(url)
            # no auto-play; el panel decide
            return True
        except Exception:
            self._ready = False
            return False

    def is_ready(self) -> bool:
        return self._ready

    def play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if self._ready:
                self.player.play()

    def stop(self):
        try:
            self.player.stop()
            self.player.setSource(QUrl())  # libera decoders
            self._ready = False
        except Exception:
            pass

    def closeEvent(self, e):
        self.stop()
        super().closeEvent(e)
