from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt


class SectionView(QWidget):
    """
    Base de secciones con:
    - Header (título + subtítulo opcional) que se puede ocultar/mostrar
    - Separador fino
    - Área de contenido expansible (self.content_layout)
    """

    def __init__(self, title: str, subtitle: str = "", *, compact: bool = True, show_header: bool = True):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 12 if compact else 24)
        root.setSpacing(10 if compact else 12)

        # --- Header ---
        self._header_widget = QWidget()
        header_lay = QVBoxLayout(self._header_widget)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(4 if compact else 8)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("SectionTitle")
        self.title_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.sub_lbl = QLabel(subtitle or "")
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setObjectName("SectionText")

        header_lay.addWidget(self.title_lbl)
        if subtitle:
            header_lay.addWidget(self.sub_lbl)

        # Separador fino
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.HLine)
        self._separator.setObjectName("SectionSeparator")
        self._separator.setFixedHeight(1)

        root.addWidget(self._header_widget)
        root.addWidget(self._separator)

        # --- Body (expansible) ---
        body = QWidget()
        body.setObjectName("SectionBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(10 if compact else 12)
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        root.addWidget(body, 1)

        # Donde las vistas hijas deben añadir su contenido
        self.content_layout = body_lay

        # Estado inicial del header
        self.set_header_visible(show_header)

    # --- API de control del header ---
    def set_header(self, *, title: Optional[str] = None, subtitle: Optional[str] = None, show_subtitle: Optional[bool] = None):
        if title is not None:
            self.title_lbl.setText(title)
        if subtitle is not None:
            self.sub_lbl.setText(subtitle or "")
        if show_subtitle is not None:
            self.sub_lbl.setVisible(bool(show_subtitle))

    def set_header_visible(self, visible: bool):
        self._header_widget.setVisible(visible)
        self._separator.setVisible(visible)
