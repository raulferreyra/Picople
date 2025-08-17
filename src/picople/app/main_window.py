# src/picople/app/main_window.py
from __future__ import annotations
from typing import List, Tuple

from PySide6.QtCore import Qt, QTimer, QSize, QSettings, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel,
    QLineEdit, QToolBar, QStatusBar, QProgressBar, QMessageBox, QStyle,
    QToolButton, QStackedWidget, QSizePolicy
)

from picople.core.theme import QSS_DARK, QSS_LIGHT
from picople.app import views
from picople.core.config import get_root_dirs
from picople.infrastructure.indexer import IndexerWorker
from pathlib import Path


# ------------------------ Constantes ------------------------ #

SECTIONS = [
    ("collection", "Colección"),
    ("favorites", "Favoritos"),
    ("albums", "Álbumes"),
    ("people", "Personas y mascotas"),
    ("things", "Cosas"),
    ("folders", "Carpetas"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Picople")
        self.resize(1200, 800)
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        # Estado persistente
        self.settings = QSettings()
        self.dark_mode = (self.settings.value("ui/theme", "dark") == "dark")

        self._build_ui()
        self._apply_theme()

        # Restaurar geometría/estado
        geom = self.settings.value("ui/geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        state = self.settings.value("ui/windowState")
        if state is not None:
            self.restoreState(state)

        # Navegar a última sección o Colección
        last = self.settings.value("ui/last_section", "collection")
        self._navigate(last if last in self._pages else "collection")

        # Primer arranque: si no hay carpetas
        if not get_root_dirs():
            QTimer.singleShot(400, self._first_run_prompt)

    # --------------------------- UI --------------------------- #
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(270)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)

        title = QLabel("Picople")
        title.setObjectName("AppTitle")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; padding: 8px 10px;")
        side_layout.addWidget(title)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text in SECTIONS:
            btn = QPushButton(text)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(self._icon_for_key(key))
            btn.setIconSize(QSize(18, 18))
            btn.clicked.connect(lambda _c, k=key: self._navigate(k))
            self.nav_buttons[key] = btn
            side_layout.addWidget(btn)

        side_layout.addStretch(1)

        # Centro: páginas
        self.stack = QStackedWidget()
        self._pages = {
            "collection": views.CollectionView(),
            "favorites":  views.FavoritesView(),
            "albums":     views.AlbumsView(),
            "people":     views.PeopleView(),
            "things":     views.ThingsView(),
            "folders":    views.FoldersView(),
            "search":     views.SearchView(),
        }
        for key in self._pages:
            self.stack.addWidget(self._pages[key])

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("SearchEdit")
        self.search_edit.setPlaceholderText("Buscar… (texto, nombre o cosa)")
        self.search_edit.setFixedWidth(380)

        self.btn_search = QToolButton()
        self.btn_search.setObjectName("ToolbarBtn")
        self.btn_search.setText("Buscar")
        self.btn_search.clicked.connect(self._on_search)

        self.btn_update = QToolButton()
        self.btn_update.setObjectName("ToolbarBtn")
        self.btn_update.setText("Actualizar")
        self.btn_update.clicked.connect(self._on_update)

        self.btn_theme = QToolButton()
        self.btn_theme.setObjectName("ToolbarBtn")
        self.btn_theme.setToolTip("Alternar tema")
        self.btn_theme.clicked.connect(self._on_toggle_theme)
        self._update_theme_icon()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.toolbar.addWidget(self.search_edit)
        self.toolbar.addWidget(self.btn_search)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.btn_update)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.btn_theme)

        # Ensamblar
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_label = QLabel("Listo")
        self.status_label.setObjectName("StatusLabel")

        self.progress_main = QProgressBar()
        self.progress_main.setFixedWidth(240)
        self.progress_main.setRange(0, 100)
        self.progress_main.setValue(0)
        self.progress_main.setToolTip("Progreso de tarea principal")
        self.progress_main.setTextVisible(False)

        self.progress_bg = QProgressBar()
        self.progress_bg.setFixedWidth(160)
        self.progress_bg.setRange(0, 0)
        self.progress_bg.hide()
        self.progress_bg.setToolTip("Trabajos en segundo plano")
        self.progress_main.setTextVisible(False)

        tag1 = QLabel("Proceso:")
        tag1.setObjectName("StatusTag")
        tag2 = QLabel("Fondo:")
        tag2.setObjectName("StatusTag")

        self.status.addWidget(self.status_label, 1)
        self.status.addPermanentWidget(tag1)
        self.status.addPermanentWidget(self.progress_main)
        self.status.addPermanentWidget(tag2)
        self.status.addPermanentWidget(self.progress_bg)

    # ------------------------ Navegación ------------------------ #
    def _navigate(self, key: str) -> None:
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        page = self._pages.get(key)
        if page:
            self.stack.setCurrentWidget(page)
            self.settings.setValue("ui/last_section", key)

    # ------------------------ Acciones ------------------------ #
    def _on_search(self) -> None:
        query = self.search_edit.text().strip()
        self._navigate("search")
        if not query:
            QMessageBox.information(
                self, "Picople", "Escribe algo para buscar.")
            return
        QMessageBox.information(
            self, "Picople", f"Buscar: '{query}' (no implementado)")

    def _on_update(self) -> None:
        roots = get_root_dirs()
        if not roots:
            QMessageBox.information(
                self, "Picople", "No hay carpetas configuradas. Ve a 'Carpetas' para agregar.")
            return

        # Deshabilitar boton mientras corre
        self.btn_update.setEnabled(False)
        self.progress_main.setValue(0)
        self.progress_bg.show()
        self.status_label.setText("Preparando indexación…")

        # Hilo + worker
        self._index_thread = QThread(self)
        self._indexer = IndexerWorker(roots, thumb_size=320)
        self._indexer.moveToThread(self._index_thread)

        # Conexiones
        self._index_thread.started.connect(self._indexer.run)
        self._indexer.started.connect(self._on_index_started)
        self._indexer.progress.connect(self._on_index_progress)
        self._indexer.info.connect(lambda msg: self.status_label.setText(msg))
        self._indexer.error.connect(self._on_index_error)
        self._indexer.finished.connect(self._on_index_finished)
        self._indexer.finished.connect(self._index_thread.quit)

        # Limpieza al terminar
        self._index_thread.finished.connect(self._indexer.deleteLater)
        self._index_thread.finished.connect(self._index_thread.deleteLater)

        self._index_thread.start()

    def _on_toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_theme()
        self._update_theme_icon()
        self.settings.setValue(
            "ui/theme", "dark" if self.dark_mode else "light")
        self.status_label.setText("Tema alternado")
        QTimer.singleShot(1200, lambda: self.status_label.setText("Listo"))

    # ------------------------ Helpers ------------------------ #
    def _apply_theme(self) -> None:
        self.setStyleSheet(QSS_DARK if self.dark_mode else QSS_LIGHT)

    def _icon_for_key(self, key: str) -> QIcon:
        style = self.style()
        mapping = {
            "collection": QStyle.SP_DirIcon,
            "favorites":  QStyle.SP_DialogYesButton,
            "albums":     QStyle.SP_FileDialogListView,
            "people":     QStyle.SP_DirHomeIcon,
            "things":     QStyle.SP_DesktopIcon,
            "folders":    QStyle.SP_DirOpenIcon,
        }
        return style.standardIcon(mapping.get(key, QStyle.SP_FileIcon))

    def _update_theme_icon(self) -> None:
        self.btn_theme.setText("🌙" if self.dark_mode else "☀")

    def _first_run_prompt(self) -> None:
        ans = QMessageBox.question(
            self, "Bienvenido a Picople",
            "Aún no has elegido carpetas para indexar.\n\n¿Deseas configurarlas ahora?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if ans == QMessageBox.Yes:
            self._navigate("folders")
            # abrir el diálogo de agregar carpeta si la vista lo soporta
            folders_view = self._pages.get("folders")
            if hasattr(folders_view, "open_add_dialog"):
                folders_view.open_add_dialog()

    def _on_index_started(self, total: int):
        self.status_label.setText(f"Indexando… 0/{total}")
        self.progress_main.setRange(0, 100)
        self.progress_main.setValue(0)

    def _on_index_progress(self, i: int, total: int, path: str):
        if total > 0:
            pct = int(i * 100 / total)
            self.progress_main.setValue(pct)
            name = Path(path).name if path else ""
            self.status_label.setText(f"Indexando… {i}/{total}  •  {name}")

    def _on_index_error(self, path: str, err: str):
        # No frenamos la cola, solo informamos en la barra (se podría loguear)
        self.status_label.setText(f"Error con {Path(path).name}: {err[:60]}")

    def _on_index_finished(self, summary: dict):
        self.progress_main.setValue(100)
        self.progress_bg.hide()
        self.btn_update.setEnabled(True)
        total = summary.get("total", 0)
        imgs = summary.get("images", 0)
        vids = summary.get("videos", 0)
        ok = summary.get("thumbs_ok", 0)
        fail = summary.get("thumbs_fail", 0)
        self.status_label.setText(
            f"Indexación lista: {total} archivos  •  {imgs} fotos / {vids} videos  •  miniaturas OK {ok}, fallos {fail}")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Listo"))

    # ------------------------ Persistencia ventana ------------------------ #

    def closeEvent(self, event) -> None:
        self.settings.setValue("ui/geometry", self.saveGeometry())
        self.settings.setValue("ui/windowState", self.saveState())
        super().closeEvent(event)
