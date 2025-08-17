from __future__ import annotations
from typing import List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtGui import QPainter, QColor
from picople.app.controllers import MediaItem
from .MediaViewerPanel import MediaViewerPanel


class ViewerOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Widget | Qt.FramelessWindowHint)
        self.setObjectName("ViewerOverlay")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        self.panel = None
        self.hide()

    def open(self, items: List[MediaItem], start_index: int = 0):
        # limpia panel anterior
        if self.panel:
            self.panel.setParent(None)
            self.panel.deleteLater()
            self.panel = None

        self.panel = MediaViewerPanel(items, start_index, parent=self)
        self.layout().addWidget(self.panel, 1)

        # cubrir el central widget del mainwindow
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def paintEvent(self, e):
        # fondo semitransparente
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 180))
        super().paintEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
            e.accept()
        else:
            super().keyPressEvent(e)
