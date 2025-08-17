# src/picople/app/views/FoldersView.py
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices

from picople.core.config import get_root_dirs, add_root_dir, remove_root_dir
from . import SectionView


class FoldersView(SectionView):
    def __init__(self):
        super().__init__("Carpetas", "Elige qué carpetas indexar (Imágenes, Descargas u otras).")

        self.list = QListWidget()
        # ✅ usar el enum de QAbstractItemView
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)

        self.btn_add = QPushButton("Agregar carpeta")
        self.btn_del = QPushButton("Quitar carpeta")
        self.btn_open = QPushButton("Abrir carpeta")

        self.btn_add.clicked.connect(self.open_add_dialog)
        self.btn_del.clicked.connect(self.remove_selected)
        self.btn_open.clicked.connect(self.open_selected)

        # Layout específico
        outer = QHBoxLayout()
        outer.setSpacing(10)

        left = QVBoxLayout()
        left.addWidget(self.list)

        right = QVBoxLayout()
        right.addWidget(self.btn_add)
        right.addWidget(self.btn_del)
        right.addWidget(self.btn_open)
        right.addStretch(1)

        outer.addLayout(left, 1)
        outer.addLayout(right)

        # Agrega al layout heredado de SectionView
        self.layout().addLayout(outer)

        self.refresh()

    # ---------- API pública ----------
    def open_add_dialog(self):
        start_dir = self._guess_start_dir()
        folder = QFileDialog.getExistingDirectory(
            self, "Selecciona una carpeta", start_dir)
        if folder:
            p = str(Path(folder).resolve())
            add_root_dir(p)
            self.refresh()

    # ---------- helpers ----------
    def refresh(self):
        self.list.clear()
        for d in get_root_dirs():
            self.list.addItem(QListWidgetItem(d))

    def remove_selected(self):
        it = self.list.currentItem()
        if not it:
            QMessageBox.information(
                self, "Carpetas", "Selecciona una carpeta para quitar.")
            return
        remove_root_dir(it.text())
        self.refresh()

    def open_selected(self):
        it = self.list.currentItem()
        if not it:
            QMessageBox.information(
                self, "Carpetas", "Selecciona una carpeta para abrir.")
            return
        # ✅ pasar un QUrl válido
        QDesktopServices.openUrl(QUrl.fromLocalFile(it.text()))

    def _guess_start_dir(self) -> str:
        pics = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        if pics:
            return pics
        dls = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if dls:
            return dls
        return str(Path.home())
