# app/main_window.py
from __future__ import annotations
from typing import Tuple
from pathlib import Path
from inspect import signature

from PySide6.QtCore import Qt, QTimer, QSize, QSettings, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel,
    QLineEdit, QToolBar, QStatusBar, QProgressBar, QMessageBox, QStyle,
    QToolButton, QStackedWidget, QSizePolicy, QInputDialog
)

from picople.core.theme import QSS_DARK, QSS_LIGHT
from picople.app import views
from picople.core.config import get_root_dirs
from picople.infrastructure.indexer import IndexerWorker
from picople.infrastructure.db import Database, DBError
from picople.core.paths import app_data_dir
from picople.app.controllers import MediaItem
from picople.app.views.ViewerOverlay import ViewerOverlay
from picople.app.views.MediaViewerPanel import MediaViewerPanel
from picople.infrastructure.face_scan import FaceScanWorker
from picople.core.log import log


SECTIONS: Tuple[Tuple[str, str], ...] = (
    ("collection", "Colección"),
    ("favorites",  "Favoritos"),
    ("albums",     "Álbumes"),
    ("people",     "Personas y mascotas"),
    ("things",     "Cosas"),
    ("folders",    "Carpetas"),
    ("settings",   "Preferencias"),
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Picople")
        self.resize(1200, 800)
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        self.settings = QSettings()
        self.dark_mode = (self.settings.value("ui/theme", "dark") == "dark")

        self._db: Database | None = None
        self._db_key: str | None = None
        self._index_thread: QThread | None = None
        self._indexer: IndexerWorker | None = None
        self._viewer_page: QWidget | None = None
        self._viewer_prev_widget: QWidget | None = None
        self._face_thread: QThread | None = None
        self._face_worker: FaceScanWorker | None = None
        self._face_timer: QTimer | None = None

        # Abrir (o crear) DB cifrada antes de construir vistas
        self._open_database_or_prompt()

        # UI
        self._build_ui()
        self._apply_theme()

        # Face-scan timer (idle)
        self._face_timer = QTimer(self)
        self._face_timer.setInterval(30_000)  # 30s
        self._face_timer.timeout.connect(self._kick_face_scan_idle)
        self._face_timer.start()

        # Restaurar estado de ventana
        geom = self.settings.value("ui/geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        state = self.settings.value("ui/windowState")
        if state is not None:
            self.restoreState(state)

        last = self.settings.value("ui/last_section", "collection")
        self._navigate(last if last in self._pages else "collection")

        if not get_root_dirs():
            QTimer.singleShot(400, self._first_run_prompt)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(270)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(12, 12, 12, 12)
        side.setSpacing(10)

        title = QLabel("Picople")
        title.setObjectName("AppTitle")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; padding: 8px 10px;")
        side.addWidget(title)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text in SECTIONS:
            b = QPushButton(text)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(self._icon_for_key(key))
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(lambda _c, k=key: self._navigate(k))
            self.nav_buttons[key] = b
            side.addWidget(b)

        side.addStretch(1)

        # centro
        self.stack = QStackedWidget()
        self.viewer_overlay = ViewerOverlay(parent=self.centralWidget())
        self.viewer_overlay.hide()

        self._pages = {
            "collection": views.CollectionView(db=self._db),
            "favorites":  views.FavoritesView(db=self._db),
            "albums":     views.AlbumsView(db=self._db),
            "people":     views.PeopleView(db=self._db),
            "things":     views.ThingsView(),
            "folders":    views.FoldersView(),
            "search":     views.SearchView(),
            "settings":   views.SettingsView(self.settings),
        }

        coll = self._pages.get("collection")
        if hasattr(coll, "openViewer"):
            coll.openViewer.connect(self._open_viewer_embedded)

        for key in self._pages:
            self.stack.addWidget(self._pages[key])

        # toolbar
        self.toolbar = QToolBar()
        self.toolbar.setObjectName("MainToolbar")
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

        self.btn_backup = QToolButton()
        self.btn_backup.setObjectName("ToolbarBtn")
        self.btn_backup.setText("Backup")
        self.btn_backup.setToolTip("Crear copia cifrada de la base de datos")
        self.btn_backup.clicked.connect(self._on_backup)

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
        self.toolbar.addWidget(self.btn_backup)

        # ensamblar
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)

        # status
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_label = QLabel("Listo")
        self.status_label.setObjectName("StatusLabel")

        self.progress_main = QProgressBar()
        self.progress_main.setFixedWidth(240)
        self.progress_main.setRange(0, 100)
        self.progress_main.setValue(0)
        self.progress_main.setTextVisible(False)

        self.progress_bg = QProgressBar()
        self.progress_bg.setFixedWidth(160)
        self.progress_bg.setRange(0, 0)
        self.progress_bg.hide()
        self.progress_bg.setTextVisible(False)

        tag1 = QLabel("Proceso:")
        tag1.setObjectName("StatusTag")
        tag2 = QLabel("Fondo:")
        tag2.setObjectName("StatusTag")

        self.status.addWidget(self.status_label, 1)
        self.status.addPermanentWidget(tag1)
        self.status.addPermanentWidget(self.progress_main)
        self.status.addPermanentWidget(tag2)
        self.status.addPermanentWidget(self.progress_bg)

    # ---------- navegación ----------
    def _navigate(self, key: str) -> None:
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        page = self._pages.get(key)
        if page:
            self.stack.setCurrentWidget(page)
            self.settings.setValue("ui/last_section", key)

    # ---------- acciones ----------
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
                self, "Picople",
                "No hay carpetas configuradas. Ve a 'Carpetas' para agregar."
            )
            return
        if not self._db or not self._db.is_open:
            QMessageBox.warning(
                self, "Picople",
                "La base de datos no está abierta. Reinicia e ingresa tu clave."
            )
            return

        thumb_sz = int(self.settings.value("indexer/thumb_size", 320))
        video_thumbs = str(self.settings.value(
            "indexer/video_thumbs", "1")) in ("1", "true", "True")

        self.btn_update.setEnabled(False)
        self.progress_main.setValue(0)
        self.progress_bg.show()
        self.status_label.setText("Preparando indexación…")

        self._index_thread = QThread(self)
        self._indexer = IndexerWorker(
            roots,
            thumb_size=thumb_sz,
            db_path=self._db.db_path,
            db_key=self._db_key,
            allow_video_thumbs=video_thumbs
        )
        self._indexer.moveToThread(self._index_thread)

        self._index_thread.started.connect(self._indexer.run)
        self._indexer.started.connect(self._on_index_started)
        self._indexer.progress.connect(self._on_index_progress)
        self._indexer.info.connect(self._on_index_info)
        self._indexer.error.connect(self._on_index_error)
        self._indexer.finished.connect(self._on_index_finished)
        self._indexer.finished.connect(self._index_thread.quit)
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

    # ---------- face scan helpers ----------
    def _kick_face_scan_idle(self):
        if not (self._db and self._db.is_open):
            return
        if self._face_thread is not None:
            # ya hay un escaneo en curso
            return

        try:
            from picople.infrastructure import face_scan as fs
            log("MainWindow: FaceScanWorker desde:", getattr(fs, "__file__", "?"),
                "sig:", str(signature(fs.FaceScanWorker)))
        except Exception as e:
            log("MainWindow: no pude inspeccionar FaceScanWorker:", e)

        log("MainWindow: creando FaceScanWorker con",
            str(self._db.db_path), "key?", bool(self._db_key))

        self._face_thread = QThread(self)
        self._face_worker = FaceScanWorker(
            str(self._db.db_path), self._db_key or "")
        self._face_worker.moveToThread(self._face_thread)

        # Conexiones: métodos miembros (GUI thread)
        self._face_thread.started.connect(self._face_worker.run)
        self._face_worker.started.connect(self._on_face_started)
        self._face_worker.progress.connect(self._on_face_progress)
        self._face_worker.info.connect(self._on_face_info)
        self._face_worker.error.connect(self._on_face_error)
        self._face_worker.finished.connect(self._on_face_finished)
        self._face_worker.finished.connect(self._face_thread.quit)

        self._face_thread.finished.connect(self._face_worker.deleteLater)
        self._face_thread.finished.connect(
            lambda: setattr(self, "_face_worker", None))
        self._face_thread.finished.connect(self._face_thread.deleteLater)
        self._face_thread.finished.connect(
            lambda: setattr(self, "_face_thread", None))

        self._face_thread.start()

    def _on_face_started(self, total: int):
        self.status_label.setText(f"Analizando caras… 0/{total}")

    def _on_face_progress(self, i: int, total: int, path: str):
        self.status_label.setText(
            f"Analizando caras… {i}/{total} • {Path(path).name}")

    def _on_face_info(self, msg: str):
        self.status_label.setText(msg)

    def _on_face_error(self, path: str, err: str):
        self.status_label.setText(
            f"Caras: error en {Path(path).name}: {err[:60]}")

    def _on_face_finished(self, summary: dict):
        self.status_label.setText(
            f"Caras: lote listo • medias {summary.get('scanned', 0)} • caras {summary.get('faces', 0)}"
        )
        # refresca PeopleView si está cargada
        page = self._pages.get("people")
        if hasattr(page, "refresh_from_db"):
            try:
                page.refresh_from_db()
            except Exception:
                pass

    # ---------- indexer callbacks ----------
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

    def _on_index_info(self, msg: str):
        self.status_label.setText(msg)

    def _on_index_error(self, path: str, err: str):
        self.status_label.setText(f"Error con {Path(path).name}: {err[:60]}")

    def _on_index_finished(self, summary: dict):
        self.progress_main.setValue(100)
        self.progress_bg.hide()
        self.btn_update.setEnabled(True)

        # reconstruir álbumes por carpetas + reparar duplicados/portadas
        try:
            roots = self.get_roots_for_albums()
            if self._db and self._db.is_open:
                self._db.rebuild_albums_from_media(roots)
                self._db.repair_albums(roots)
        except Exception:
            pass

        # refresca "albums" después
        page = self._pages.get("albums")
        if hasattr(page, "refresh"):
            page.refresh()

        # refrescar vistas
        for key in ("collection", "favorites", "albums"):
            page = self._pages.get(key)
            if hasattr(page, "refresh"):
                if key == "collection":
                    page.refresh(reset=True)
                else:
                    page.refresh()

        total = summary.get("total", 0)
        imgs = summary.get("images", 0)
        vids = summary.get("videos", 0)
        ok = summary.get("thumbs_ok", 0)
        fail = summary.get("thumbs_fail", 0)
        self.status_label.setText(
            f"Indexación lista: {total} archivos  •  {imgs} fotos / {vids} videos  •  miniaturas OK {ok}, fallos {fail}"
        )
        QTimer.singleShot(2000, lambda: self.status_label.setText("Listo"))
        self._kick_face_scan_idle()

    # ---------- helpers ----------
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
            "settings":   QStyle.SP_FileDialogDetailedView,
        }
        return style.standardIcon(mapping.get(key, QStyle.SP_FileIcon))

    def _first_run_prompt(self) -> None:
        ans = QMessageBox.question(
            self, "Bienvenido a Picople",
            "Aún no has elegido carpetas para indexar.\n\n¿Deseas configurarlas ahora?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if ans == QMessageBox.Yes:
            self._navigate("folders")
            folders_view = self._pages.get("folders")
            if hasattr(folders_view, "open_add_dialog"):
                folders_view.open_add_dialog()

    def _open_database_or_prompt(self) -> None:
        # Ruta de la DB cifrada
        db_dir = app_data_dir() / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "picople.db"

        self._db = Database(db_path)

        if not db_path.exists():
            # Crear nueva base cifrada
            pw, ok = QInputDialog.getText(
                self, "Crear seguridad",
                "Crea una clave para cifrar la base de datos:",
                echo=QLineEdit.Password
            )
            if not ok or not pw:
                QMessageBox.warning(
                    self, "Picople", "Se necesita una clave para crear la base cifrada.")
                self._db = None
                self._db_key = None
                return
            try:
                self._db.open(pw)
                self._db_key = pw

                # Warm-up PeopleStore (migraciones/limpieza) y reparación de álbumes
                try:
                    from picople.infrastructure.people_store import PeopleStore
                    ps = PeopleStore(self._db)
                    ps.purge_empty_persons()
                except Exception as e:
                    log("MainWindow: warmup PeopleStore falló:", e)

                try:
                    roots = self.get_roots_for_albums()
                    self._db.repair_albums(roots)
                except Exception:
                    pass

                QMessageBox.information(
                    self, "Picople", "Base de datos cifrada creada correctamente.")
            except DBError as e:
                QMessageBox.critical(self, "Picople", str(e))
                self._db = None
                self._db_key = None
                return
        else:
            # Abrir base existente
            pw, ok = QInputDialog.getText(
                self, "Desbloquear seguridad",
                "Ingresa la clave de la base de datos:",
                echo=QLineEdit.Password
            )
            if not ok or not pw:
                QMessageBox.warning(
                    self, "Picople", "No se pudo abrir la base de datos cifrada.")
                self._db = None
                self._db_key = None
                return
            try:
                self._db.open(pw)
                self._db_key = pw

                # Warm-up migraciones/limpieza al abrir BD existente
                try:
                    from picople.infrastructure.people_store import PeopleStore
                    ps = PeopleStore(self._db)
                    ps.purge_empty_persons()
                except Exception as e:
                    log("MainWindow: warmup PeopleStore falló:", e)

                # Reparación de álbumes tras abrir
                try:
                    roots = self.get_roots_for_albums()
                    self._db.repair_albums(roots)
                except Exception as e:
                    log("[albums] repair on open failed:", e)

            except DBError as e:
                QMessageBox.critical(self, "Picople", str(e))
                self._db = None
                self._db_key = None

    def _on_backup(self):
        QMessageBox.information(self, "Picople", "Backup aún no implementado.")

    # Helpers de albums
    def get_roots_for_albums(self) -> list[str]:
        from picople.core.config import get_root_dirs
        return get_root_dirs()

    # ---------- cierre ----------
    def closeEvent(self, event) -> None:
        # detener indexer
        try:
            if self._index_thread and self._index_thread.isRunning():
                self.status_label.setText("Cerrando tareas en segundo plano…")
                if self._indexer:
                    try:
                        self._indexer.cancel()
                    except Exception:
                        pass
                self._index_thread.quit()
                self._index_thread.wait(5000)
        except Exception:
            pass

        # detener face scan
        try:
            if self._face_thread and self._face_thread.isRunning():
                self.status_label.setText("Cerrando análisis de caras…")
                if self._face_worker:
                    try:
                        self._face_worker.cancel()
                    except Exception:
                        pass
                self._face_thread.quit()
                self._face_thread.wait(5000)
        except Exception:
            pass

        self.settings.setValue("ui/geometry", self.saveGeometry())
        self.settings.setValue("ui/windowState", self.saveState())
        super().closeEvent(event)
