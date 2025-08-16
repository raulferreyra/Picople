# ─────────────────────────────────────────────────────────────────────────────
# File: src/picople/app/main_window.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, QTimer, QSize, QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QPushButton,
    QLabel,
    QLineEdit,
    QToolBar,
    QStatusBar,
    QProgressBar,
    QMessageBox,
    QStyle,
    QToolButton,
    QStackedWidget,
    QSizePolicy,
)

from picople.core.theme import QSS_DARK, QSS_LIGHT
from picople.app import views


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

        # Estado persistente (tema, geometría, última sección)
        self.settings = QSettings()
        self.dark_mode = (self.settings.value("ui/theme", "dark") == "dark")

        self._build_ui()
        self._apply_theme()

        # Restaurar geometría/estado de ventana
        geom = self.settings.value("ui/geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        state = self.settings.value("ui/windowState")
        if state is not None:
            self.restoreState(state)

        # Navegar a la última sección (o colección por defecto)
        last = self.settings.value("ui/last_section", "collection")
        self._navigate(last if last in self.pages else "collection")

    # --------------------------- UI Builders --------------------------- #
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

        # Botones del menú (con IDs para QSS)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text in SECTIONS:
            btn = QPushButton(text)
            btn.setObjectName("NavButton")           # <- coincide con QSS
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(self._icon_for_key(key))
            btn.setIconSize(QSize(18, 18))
            btn.clicked.connect(lambda _checked, k=key: self._navigate(k))
            self.nav_buttons[key] = btn
            side_layout.addWidget(btn)

        side_layout.addStretch(1)

        # Área central: router de páginas
        self.stack = QStackedWidget()
        self.pages = {
            "collection": views.CollectionView(),
            "favorites":  views.FavoritesView(),
            "albums":     views.AlbumsView(),
            "people":     views.PeopleView(),
            "things":     views.ThingsView(),
            "folders":    views.FoldersView(),
            "search":     views.SearchView(),
        }
        for key in self.pages:
            self.stack.addWidget(self.pages[key])

        # Toolbar (top)
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("SearchEdit")  # <- coincide con QSS
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

        # Toggle de tema (solo ícono)
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

        # Ensamblar centro
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)

        # Status bar con dos progresos
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_label = QLabel("Listo")
        self.status_label.setObjectName("StatusLabel")

        self.progress_main = QProgressBar()
        self.progress_main.setFixedWidth(240)
        self.progress_main.setRange(0, 100)
        self.progress_main.setValue(0)
        self.progress_main.setToolTip("Progreso de tarea principal")

        self.progress_bg = QProgressBar()
        self.progress_bg.setFixedWidth(160)
        self.progress_bg.setRange(0, 0)
        self.progress_bg.hide()
        self.progress_bg.setToolTip("Trabajos en segundo plano")

        tag1 = QLabel("Proceso:")
        tag1.setObjectName("StatusTag")
        tag2 = QLabel("Fondo:")
        tag2.setObjectName("StatusTag")

        self.status.addWidget(self.status_label, 1)
        self.status.addPermanentWidget(tag1)
        self.status.addPermanentWidget(self.progress_main)
        self.status.addPermanentWidget(tag2)
        self.status.addPermanentWidget(self.progress_bg)

    # ----------------------------- Navegación ---------------------------- #
    def _navigate(self, key: str) -> None:
        # marcar botón activo
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        # cambiar página si existe
        page = self.pages.get(key)
        if page:
            self.stack.setCurrentWidget(page)
            self.settings.setValue("ui/last_section", key)

    # ----------------------------- Actions ---------------------------- #
    def _alert_not_implemented(self, name: str) -> None:
        QMessageBox.information(
            self, "Picople", f"Botón de '{name}', no implementado")

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
        steps: List[Tuple[str, int]] = [
            ("Leyendo datos de importación…", 20),
            ("Corrigiendo caras…", 45),
            ("Arreglando lugares…", 70),
            ("Actualizando índices…", 90),
        ]
        self.status_label.setText("Iniciando actualización…")
        self.progress_main.setValue(0)
        self.progress_bg.show()

        def run_steps(i: int = 0) -> None:
            if i >= len(steps):
                self.progress_main.setValue(100)
                self.status_label.setText("Listo")
                QTimer.singleShot(600, lambda: self.progress_main.setValue(0))
                self.progress_bg.hide()
                return
            msg, val = steps[i]
            self.status_label.setText(msg)
            self.progress_main.setValue(val)
            QTimer.singleShot(600, lambda: run_steps(i + 1))

        run_steps(0)

    def _on_toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_theme()
        self._update_theme_icon()
        self.settings.setValue(
            "ui/theme", "dark" if self.dark_mode else "light")
        self.status_label.setText("Tema alternado")
        QTimer.singleShot(1200, lambda: self.status_label.setText("Listo"))

    # ----------------------------- Helpers ---------------------------- #
    def _apply_theme(self) -> None:
        self.setStyleSheet(QSS_DARK if self.dark_mode else QSS_LIGHT)

    def _icon_for_key(self, key: str) -> QIcon:
        style = self.style()
        mapping = {
            "collection": QStyle.SP_DirIcon,
            "favorites": QStyle.SP_DialogYesButton,
            "albums": QStyle.SP_FileDialogListView,
            "people": QStyle.SP_DirHomeIcon,
            "things": QStyle.SP_DesktopIcon,
            "folders": QStyle.SP_DirOpenIcon,
        }
        return style.standardIcon(mapping.get(key, QStyle.SP_FileIcon))

    def _update_theme_icon(self) -> None:
        # Mostramos el ícono del modo actual (🌙 cuando está oscuro, ☀ cuando está claro)
        self.btn_theme.setText("🌙" if self.dark_mode else "☀")

    # ----------------------------- Persistencia ---------------------------- #
    def closeEvent(self, event) -> None:
        self.settings.setValue("ui/geometry", self.saveGeometry())
        self.settings.setValue("ui/windowState", self.saveState())
        super().closeEvent(event)
