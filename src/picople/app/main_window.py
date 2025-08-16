# ─────────────────────────────────────────────────────────────────────────────
# File: src/picople/app/main_window.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QIcon
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
)

from picople.core.theme import QSS_DARK, QSS_LIGHT


class MainWindow(QMainWindow):
    def __init__(self, *, start_dark: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("Picople")
        self.resize(1200, 800)
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        self._is_dark = start_dark

        self._build_ui()
        self.apply_theme()

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
        side_layout.setSpacing(8)

        title = QLabel("Picople")
        title.setObjectName("AppTitle")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; padding: 8px 10px;")
        side_layout.addWidget(title)

        # Menu buttons (más aire entre ellos vía QSS y spacing del layout)
        self.btn_collection = self._menu_button("Colección", "coleccion")
        self.btn_favs = self._menu_button("Favoritos", "favoritos")
        self.btn_albums = self._menu_button("Álbumes", "albumes")
        self.btn_people = self._menu_button(
            "Personas y mascotas", "personas_mascotas")
        self.btn_things = self._menu_button("Cosas", "cosas")
        self.btn_folders = self._menu_button("Carpetas", "carpetas")

        for w in [self.btn_collection, self.btn_favs, self.btn_albums, self.btn_people, self.btn_things, self.btn_folders]:
            side_layout.addWidget(w)
        side_layout.addStretch(1)

        # Content area placeholder (más márgenes y spacing)
        self.content = QFrame()
        self.content.setObjectName("Content")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(28, 20, 28, 24)
        content_layout.setSpacing(14)

        # Toolbar (top)
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("SearchBox")
        self.search_edit.setPlaceholderText("Buscar… (texto, nombre o cosa)")
        self.search_edit.setFixedWidth(380)

        self.action_search = QPushButton("Buscar")
        self.action_search.setObjectName("ToolbarBtn")
        self.action_search.clicked.connect(self._on_search)
        self.action_update = QPushButton("Actualizar")
        self.action_update.setObjectName("ToolbarBtn")
        self.action_update.clicked.connect(self._on_update)

        # Toggle de tema como botón con ícono (sin texto)
        self.btn_theme = QToolButton()
        self.btn_theme.setObjectName("ThemeToggle")
        self.btn_theme.setCheckable(True)
        self.btn_theme.setChecked(self._is_dark)
        self._refresh_theme_icon()  # fija ☀︎/🌙 según estado
        self.btn_theme.setToolTip("Alternar tema")
        self.btn_theme.clicked.connect(self._on_toggle_theme)

        self.toolbar.addWidget(self.search_edit)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.action_search)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.action_update)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.btn_theme)

        # Welcome label (color gobernado por QSS, no negro)
        self.welcome = QLabel("""
            <div style='text-align:center;'>
                <h2>Bienvenido a Picople</h2>
                <p>Hito 1: Interfaz base, menú con alerts y barras de progreso.</p>
            </div>
        """)
        self.welcome.setObjectName("WelcomeLabel")
        self.welcome.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.welcome, alignment=Qt.AlignCenter)

        # Assemble layout
        layout.addWidget(self.sidebar)
        layout.addWidget(self.content, 1)

        # Status bar with two progress bars y etiquetas legibles
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

    def _menu_button(self, text: str, key: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("MenuBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIcon(self._icon_for_key(key))
        btn.setIconSize(QSize(18, 18))
        btn.clicked.connect(lambda: self._alert_not_implemented(text))
        return btn

    # ----------------------------- Actions ---------------------------- #
    def _alert_not_implemented(self, name: str) -> None:
        QMessageBox.information(
            self, "Picople", f"Botón de '{name}', no implementado")

    def _on_search(self) -> None:
        query = self.search_edit.text().strip()
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
        self._is_dark = not self._is_dark
        self.apply_theme()
        self._refresh_theme_icon()
        QTimer.singleShot(1200, lambda: self.status_label.setText("Listo"))
        self.status_label.setText("Tema alternado")

    # ----------------------------- Helpers ---------------------------- #
    def apply_theme(self) -> None:
        self.setStyleSheet(QSS_DARK if self._is_dark else QSS_LIGHT)

    def _icon_for_key(self, key: str) -> QIcon:
        style = self.style()
        mapping = {
            "coleccion": QStyle.SP_DirIcon,
            "favoritos": QStyle.SP_DialogYesButton,
            "albumes": QStyle.SP_FileDialogListView,
            "personas_mascotas": QStyle.SP_DirHomeIcon,
            "cosas": QStyle.SP_DesktopIcon,
            "carpetas": QStyle.SP_DirOpenIcon,
        }
        return style.standardIcon(mapping.get(key, QStyle.SP_FileIcon))

    def _refresh_theme_icon(self) -> None:
        # Mostrar icono según estado actual (🌙 indica "tocar para ir a oscuro" o viceversa)
        # Decisión: mostramos el ícono del MODO DESTINO (más claro para el usuario)
        # Si estamos en oscuro, mostramos ☀ para sugerir pasar a claro; si estamos en claro, mostramos 🌙.
        self.btn_theme.setText("☀" if self._is_dark else "🌙")
