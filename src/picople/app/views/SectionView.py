# src/picople/app/views/SectionView.py
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class SectionView(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("SectionTitle")
        self.title_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.sub_lbl = QLabel(
            subtitle or "Vista placeholder. Funcionalidad aún no implementada.")
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setObjectName("SectionText")

        lay.addWidget(self.title_lbl)
        lay.addWidget(self.sub_lbl)
        lay.addStretch(1)
