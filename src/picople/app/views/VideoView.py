from __future__ import annotations
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from picople.core.log import log


class VideoView(QWidget):
    positionChanged = Signal(int)     # ms
    durationChanged = Signal(int)     # ms
    mutedChanged = Signal(bool)
    volumeChanged = Signal(int)     # 0..100
    playingChanged = Signal(bool)    # True si en reproducción

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        lay.addWidget(self.video_widget)

        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)

        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video_widget)
        self.player.setAudioOutput(self.audio)

        self._ready = False
        self._pending_play = False

        # Conexiones
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.errorOccurred.connect(self._on_error)
        self.player.positionChanged.connect(
            lambda p: (self.positionChanged.emit(p), None))
        self.player.durationChanged.connect(
            lambda d: (self.durationChanged.emit(d), None))

    # -------- Internos / logs --------
    def _on_status(self, st):
        self._ready = st in (QMediaPlayer.LoadedMedia,
                             QMediaPlayer.BufferedMedia)
        if self._ready and self._pending_play:
            self._pending_play = False
            try:
                self.player.play()
            except Exception as e:
                log("VideoView.autoplay EXC:", e)

    def _on_state(self, st):
        is_playing = (st == QMediaPlayer.PlayingState)
        self.playingChanged.emit(is_playing)

    def _on_error(self, err, msg):
        try:
            self.player.stop()
            self.player.setSource(QUrl())
        except Exception:
            pass
        self._ready = False
        self._pending_play = False
        self.playingChanged.emit(False)

    # -------- API pública --------
    def load_path(self, path: str) -> bool:
        try:
            self._pending_play = False
            self.player.stop()
            self.player.setSource(QUrl())
            self._ready = False

            url = QUrl.fromLocalFile(path)
            self.player.setSource(url)
            return True
        except Exception as e:
            log("VideoView.load EXC:", e)
            self._ready = False
            self._pending_play = False
            return False

    def is_ready(self) -> bool:
        return self._ready

    def play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if not self._ready:
                self._pending_play = True
            try:
                self.player.play()
            except Exception as e:
                log("VideoView.play EXC:", e)

    def set_position(self, ms: int):
        try:
            self.player.setPosition(max(0, ms))
        except Exception as e:
            log("VideoView.set_position EXC:", e)

    def set_volume(self, vol: int):
        vol = max(0, min(100, vol))
        try:
            self.audio.setVolume(vol/100.0)
            self.volumeChanged.emit(vol)
        except Exception as e:
            log("VideoView.set_volume EXC:", e)

    def toggle_mute(self):
        try:
            self.audio.setMuted(not self.audio.isMuted())
            self.mutedChanged.emit(self.audio.isMuted())
        except Exception as e:
            log("VideoView.toggle_mute EXC:", e)

    def stop(self):
        try:
            self._pending_play = False
            self.player.stop()
            self.player.setSource(QUrl())
            self._ready = False
            self.playingChanged.emit(False)
        except Exception as e:
            log("VideoView.stop EXC:", e)

    def closeEvent(self, e):
        self.stop()
        super().closeEvent(e)
