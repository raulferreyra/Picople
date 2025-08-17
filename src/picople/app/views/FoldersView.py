# src/picople/app/views/FoldersView.py
from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QFileDialog, QMessageBox, QAbstractItemView, QToolButton
)
from PySide6.QtCore import Qt, QStandardPaths, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QFontMetrics
from PySide6.QtWidgets import QApplication, QStyle

from picople.core.config import get_root_dirs, add_root_dir, remove_root_dir
from .SectionView import SectionView


class FoldersView(SectionView):
    """Vista de carpetas en modo iconos (grilla)."""

    def __init__(self):
        # Header compacto: mantenemos título/subtitulo, pero quitamos el stretch del SectionView
        super().__init__("Carpetas", "Elige qué carpetas indexar (Imágenes, Descargas u otras).")
        self._remove_trailing_stretch_from_section_layout()

        # --- Barra de acciones: + / eliminar / abrir ---
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.btn_add = QToolButton()
        self.btn_add.setIcon(self._style().standardIcon(
            QStyle.SP_FileDialogNewFolder))
        self.btn_add.setText("+")
        self.btn_add.setToolTip("Agregar carpeta")
        self.btn_add.setAutoRaise(True)
        self.btn_add.clicked.connect(self.open_add_dialog)

        self.btn_del = QToolButton()
        self.btn_del.setIcon(self._style().standardIcon(QStyle.SP_TrashIcon))
        self.btn_del.setToolTip("Quitar carpetas seleccionadas")
        self.btn_del.setAutoRaise(True)
        self.btn_del.clicked.connect(self.remove_selected)

        self.btn_open = QToolButton()
        self.btn_open.setIcon(
            self._style().standardIcon(QStyle.SP_DirOpenIcon))
        self.btn_open.setToolTip("Abrir carpeta seleccionada")
        self.btn_open.setAutoRaise(True)
        self.btn_open.clicked.connect(self.open_selected)

        actions_row.addWidget(self.btn_add)
        actions_row.addWidget(self.btn_del)
        actions_row.addWidget(self.btn_open)
        actions_row.addStretch(1)

        # --- Lista en modo Iconos (grilla) con scroll ---
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setMovement(QListWidget.Static)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setWrapping(True)
        self.list.setWordWrap(True)  # permite texto en 2 líneas si hace falta
        self.list.setIconSize(QSize(48, 48))  # icono no muy grande
        self.list.setSpacing(12)
        self.list.setUniformItemSizes(False)
        self.list.setSelectionMode(
            QAbstractItemView.ExtendedSelection)  # múltiple
        self.list.itemSelectionChanged.connect(self._on_selection_changed)

        # Tamaño de celda “target”: se recalcula en resizeEvent para tender a 7 columnas
        self._target_cols = 7
        self._tile_w = 160
        self._tile_h = 110
        self.list.setGridSize(QSize(self._tile_w, self._tile_h))

        # Ensamble en el layout del SectionView (debajo del subtítulo)
        lay = self.layout()
        lay.addLayout(actions_row)
        # ocupa todo el resto (con scrollbar si hace falta)
        lay.addWidget(self.list, 1)

        # Cargar datos iniciales
        self.refresh()
        self._on_selection_changed()

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
        icon = self._style().standardIcon(QStyle.SP_DirIcon)

        paths: List[str] = get_root_dirs()
        fm = QFontMetrics(self.list.font())
        # ancho de texto útil dentro de la celda
        text_width = max(60, self._tile_w - 16)

        for p in paths:
            p_path = Path(p)
            folder_name = p_path.name or str(p_path.drive) or p  # fallback
            # elide medio para la ruta
            short_path = fm.elidedText(p, Qt.ElideMiddle, text_width)

            # Mostramos nombre y una segunda línea con ruta elidida
            # (Si en tu sistema no respeta el salto de línea, deja solo folder_name y usa tooltip)
            label = f"{folder_name}\n{short_path}"

            it = QListWidgetItem(icon, label)
            it.setData(Qt.UserRole, p)           # ruta real
            it.setToolTip(p)                     # tooltip con ruta completa
            # texto centrado bajo el icono
            it.setTextAlignment(Qt.AlignHCenter)
            self.list.addItem(it)

        self._on_selection_changed()

    def remove_selected(self):
        selected = self.list.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "Carpetas", "Selecciona al menos una carpeta para quitar.")
            return
        for it in selected:
            remove_root_dir(str(it.data(Qt.UserRole)))
        self.refresh()

    def open_selected(self):
        selected = self.list.selectedItems()
        if len(selected) != 1:
            return
        path = str(selected[0].data(Qt.UserRole))
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _guess_start_dir(self) -> str:
        pics = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        if pics:
            return pics
        dls = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if dls:
            return dls
        return str(Path.home())

    def _on_selection_changed(self):
        count = len(self.list.selectedItems())
        # Abrir solo visible cuando hay exactamente una carpeta seleccionada
        self.btn_open.setVisible(count == 1)
        # Eliminar habilitado solo si hay selección
        self.btn_del.setEnabled(count >= 1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Recalcula el tamaño de celda para tender a _target_cols columnas según ancho disponible
        vp = self.list.viewport().width() or self.list.width()
        if vp <= 0:
            return
        spacing = self.list.spacing() or 12
        # ancho disponible descontando márgenes aproximados
        # + un pequeño colchón para que no corte textos
        tile_w = max(
            140, int((vp - (self._target_cols + 1) * spacing) / self._target_cols))
        tile_h = max(100, self._tile_h)
        if tile_w != self._tile_w:
            self._tile_w = tile_w
            self.list.setGridSize(QSize(self._tile_w, tile_h))
            # Recalcular elidido de rutas para el nuevo ancho
            self._reelide_labels()

    def _reelide_labels(self):
        fm = QFontMetrics(self.list.font())
        text_width = max(60, self._tile_w - 16)
        for i in range(self.list.count()):
            it = self.list.item(i)
            full = str(it.data(Qt.UserRole))
            folder_name = Path(full).name or full
            short_path = fm.elidedText(full, Qt.ElideMiddle, text_width)
            it.setText(f"{folder_name}\n{short_path}")

    def _remove_trailing_stretch_from_section_layout(self):
        """Quita el stretch agregado por SectionView para que el header no ocupe 60%."""
        lay = self.layout()
        # Si el último item es un QSpacerItem, lo quitamos.
        if lay is None:
            return
        idx = lay.count() - 1
        if idx >= 0:
            item = lay.itemAt(idx)
            # QSpacerItem no tiene widget; esto basta como heurística
            if item is not None and item.widget() is None and item.spacerItem() is not None:
                lay.takeAt(idx)

    def _style(self):
        return QApplication.style()
