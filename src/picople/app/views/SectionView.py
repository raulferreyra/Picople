from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt


class SectionView(QWidget):
    """
    Base de secciones con:
    - Header compacto (título + subtítulo opcional)
    - Separador fino
    - Área de contenido expansible (self.content_layout)
    """

    def __init__(self, title: str, subtitle: str = "", *, compact: bool = True):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 12 if compact else 24)
        root.setSpacing(10 if compact else 12)

        # --- Header ---
        header = QWidget()
        header_lay = QVBoxLayout(header)
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
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("SectionSeparator")
        sep.setFixedHeight(1)

        root.addWidget(header)
        root.addWidget(sep)

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
