from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from picople.core.log import log


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        lay.addWidget(self.video_widget)

        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)  # volumen por defecto
        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video_widget)
        self.player.setAudioOutput(self.audio)

        self._ready = False
        self._pending_play = False  # si el usuario presiona play antes de estar listo

        # Señales y logs
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.errorOccurred.connect(self._on_error)

    # ---------- Logs de estado ----------
    def _on_status(self, st):
        self._ready = st in (QMediaPlayer.LoadedMedia,
                             QMediaPlayer.BufferedMedia)
        log("VideoView.status:", st.name if hasattr(
            st, "name") else st, "ready:", self._ready)
        if self._ready and self._pending_play:
            log("VideoView:", "autoplay tras ready")
            self._pending_play = False
            try:
                self.player.play()
            except Exception as e:
                log("VideoView:", "autoplay error:", e)

    def _on_state(self, st):
        try:
            name = st.name  # PySide6 enum
        except Exception:
            name = str(st)
        log("VideoView.playbackState:", name)

    def _on_error(self, err, msg):
        # En algunos builds msg puede venir vacío; igual logueamos
        try:
            ename = err.name
        except Exception:
            ename = str(err)
        log("VideoView.ERROR:", ename, "|", msg)
        # Asegura liberar fuente para evitar inconsistencias
        try:
            self.player.stop()
            self.player.setSource(QUrl())
        except Exception:
            pass
        self._ready = False
        self._pending_play = False

    # ---------- API ----------
    def load_path(self, path: str) -> bool:
        try:
            # SIEMPRE parar y limpiar antes de nueva fuente
            self._pending_play = False
            self.player.stop()
            self.player.setSource(QUrl())
            self._ready = False

            url = QUrl.fromLocalFile(path)
            log("VideoView.load:", path)
            self.player.setSource(url)
            # No auto-play: el panel decide. ⏯ funcionará aún sin ready.
            return True
        except Exception as e:
            log("VideoView.load: EXCEPTION", e)
            self._ready = False
            self._pending_play = False
            return False

    def is_ready(self) -> bool:
        return self._ready

    def play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            log("VideoView:", "pause()")
            self.player.pause()
        else:
            # Si no está listo todavía, marca “pendiente” y deja que _on_status haga play cuando cargue.
            if not self._ready:
                log("VideoView:", "play solicitado pero no ready → pending")
                self._pending_play = True
            else:
                log("VideoView:", "play()")
            try:
                self.player.play()
            except Exception as e:
                log("VideoView.play EXCEPTION:", e)

    def stop(self):
        try:
            log("VideoView:", "stop() + release source")
            self._pending_play = False
            self.player.stop()
            self.player.setSource(QUrl())
            self._ready = False
        except Exception as e:
            log("VideoView.stop EXCEPTION:", e)

    def closeEvent(self, e):
        self.stop()
        super().closeEvent(e)
