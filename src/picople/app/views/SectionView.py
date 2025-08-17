from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class SectionView(QWidget):
    def __init__(self, title: str, subtitle: str = "", *, compact: bool = True):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 12 if compact else 24)
        lay.setSpacing(8 if compact else 12)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("SectionTitle")
        self.title_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.sub_lbl = QLabel(subtitle or "")
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setObjectName("SectionText")

        lay.addWidget(self.title_lbl)
        if subtitle:
            lay.addWidget(self.sub_lbl)

        # 🟢 Compacto por defecto: sin stretch (no empuja el contenido hacia abajo)
        if not compact:
            lay.addStretch(1)
