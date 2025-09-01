from __future__ import annotations
from typing import Dict, Any, Optional, List

from PySide6.QtCore import Qt, QSize, QModelIndex, QPoint, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QStackedWidget, QToolButton,
    QLabel, QStyle, QMenu, QInputDialog
)

from picople.infrastructure.db import Database
from picople.infrastructure.people_store import PeopleStore
from .SectionView import SectionView
from .PersonDetailView import PersonDetailView

ROLE_DATA = Qt.UserRole + 100
TILE = 128


class PeopleView(SectionView):
    def __init__(self, db: Optional[Database] = None):
        super().__init__(
            "Personas y mascotas",
            "Agrupación por caras (personas) y mascotas.",
            compact=True, show_header=True
        )
        self.db = db
        self.store: Optional[PeopleStore] = None
        try:
            if self.db and self.db.is_open:
                self.store = PeopleStore(self.db)
        except Exception as e:
            print(f"[PeopleView] PeopleStore init failed: {e}")
            self.store = None

        self.stack = QStackedWidget(self)
        self._page_list = QWidget(self)
        self._page_detail = QWidget(self)

        self._clusters_mock: list[Dict[str, Any]] = self._mock_clusters()
        self._current_person_id: Optional[str] = None

        self._build_list_page()
        self._build_detail_page()

        self.stack.addWidget(self._page_list)
        self.stack.addWidget(self._page_detail)
        self.content_layout.addWidget(self.stack, 1)

        self._render_guard = QTimer(self)
        self._render_guard.setInterval(2000)
        self._render_guard.timeout.connect(self._render_guard_tick)
        self._render_guard.start()

        self._reload_list()

    def _render_guard_tick(self):
        if self.stack.currentWidget() is self._page_list and self.model.rowCount() == 0:
            self._reload_list()

    # ───────────────────────── List page ─────────────────────────
    def _build_list_page(self) -> None:
        root = QVBoxLayout(self._page_list)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.list = QListView(self._page_list)
        self.list.setViewMode(QListView.IconMode)
        self.list.setSpacing(22)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(QSize(TILE, TILE))
        self.list.setUniformItemSizes(False)
        self.list.setWordWrap(True)
        self.list.doubleClicked.connect(self._on_double_clicked)

        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._open_context_menu)

        self.model = QStandardItemModel(self.list)
        self.list.setModel(self.model)

        root.addWidget(self.list, 1)

    def _circular_pixmap(self, cover_path: str | None) -> QPixmap:
        size = TILE
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        src = QPixmap(cover_path or "")
        if src.isNull():
            src = QPixmap(size, size)
            src.fill(Qt.darkGray)
        src = src.scaled(
            size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, src)
        painter.end()
        return pm

    def _reload_list(self) -> None:
        """Carga desde DB si hay store; si no, usa mock."""
        self.model.clear()

        # Reintento perezoso
        if self.store is None and self.db and self.db.is_open:
            try:
                self.store = PeopleStore(self.db)
                print("[PeopleView] PeopleStore attached on reload.")
            except Exception as e:
                print(f"[PeopleView] PeopleStore attach failed on reload: {e}")
                self.store = None

        persons: List[Dict[str, Any]]
        if self.store:
            persons = self.store.list_persons_overview(include_zero=False)
        else:
            persons = self._clusters_mock

        for p in persons:
            pm = self._circular_pixmap(p.get("cover"))
            icon = QIcon(pm)
            title = (p.get("title") or "").strip() or "Agregar nombre"
            photos = int(p.get("photos", p.get("suggestions_count", 0)))
            text = f"{title}\n{photos} foto{'s' if photos != 1 else ''}"
            it = QStandardItem(icon, text)
            it.setEditable(False)
            it.setData(p, ROLE_DATA)
            self.model.appendRow(it)

        fm = self.list.fontMetrics()
        # doble línea de texto
        two_lines = fm.height() * 2 + 6
        cell_h = 12 + TILE + 8 + two_lines + 8
        cell_w = 10 + TILE + 10
        self.list.setGridSize(QSize(cell_w, int(cell_h)))
        # refresco suave
        QTimer.singleShot(
            0, lambda: self.list.setGridSize(self.list.gridSize()))

    # ──────────────────────── Detail page ────────────────────────
    def _build_detail_page(self) -> None:
        root = QVBoxLayout(self._page_detail)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(8)

        self.btn_back = QToolButton(self._page_detail)
        self.btn_back.setObjectName("ToolbarBtn")
        self.btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_back.clicked.connect(self._on_back_clicked)

        lbl = QLabel("Sugerencias y elementos", self._page_detail)
        lbl.setObjectName("SectionText")

        hdr.addWidget(self.btn_back)
        hdr.addWidget(lbl, 1)
        root.addLayout(hdr)

        self.detail_container = QStackedWidget(self._page_detail)
        root.addWidget(self.detail_container, 1)

    def _on_back_clicked(self) -> None:
        current = self.detail_container.currentWidget()
        if isinstance(current, PersonDetailView) and current.is_on_suggestions():
            current.show_all()
            return
        self._go_back_to_list()

    def _go_back_to_list(self) -> None:
        while self.detail_container.count():
            w = self.detail_container.widget(0)
            self.detail_container.removeWidget(w)
            w.deleteLater()
        self._current_person_id = None
        self.stack.setCurrentIndex(0)
        self.set_header_visible(True)

    def _on_double_clicked(self, idx: QModelIndex) -> None:
        data: Dict[str, Any] = idx.data(ROLE_DATA)
        if not data:
            return
        pid = str(data.get("id", ""))
        title = (data.get("title") or "").strip()
        if not title:
            # si no tiene nombre, doble clic renombra
            self._rename_person(idx)
            return

        self._current_person_id = pid
        self.set_header_visible(False)

        while self.detail_container.count():
            w = self.detail_container.widget(0)
            self.detail_container.removeWidget(w)
            w.deleteLater()

        if self.store:
            detail = PersonDetailView(
                person_id=int(pid), person_title=title, store=self.store, parent=self._page_detail
            )
        else:
            detail = PersonDetailView(cluster=data, parent=self._page_detail)

        # sincronizar cambios
        detail.suggestionCountChanged.connect(
            lambda n, _pid=pid: self._update_person_label(_pid, n))
        detail.titleChanged.connect(
            lambda new_title, _pid=pid: self._apply_title_change(_pid, new_title))
        detail.coverChanged.connect(
            lambda _pid=pid: self._refresh_person_icon(_pid))

        self.detail_container.addWidget(detail)
        self.detail_container.setCurrentWidget(detail)
        self.stack.setCurrentIndex(1)

    # ─────────────────────── Menú contextual ───────────────────────
    def _open_context_menu(self, pos: QPoint) -> None:
        idx = self.list.indexAt(pos)
        if not idx.isValid():
            return
        data: Dict[str, Any] = idx.data(ROLE_DATA) or {}
        pid = data.get("id")
        if pid is None:
            return

        menu = QMenu(self)
        act_rename = menu.addAction("Renombrar…")
        if bool(data.get("is_pet")):
            act_pet = menu.addAction("Marcar como persona")
        else:
            act_pet = menu.addAction("Marcar como mascota")
        menu.addSeparator()
        act_delete = menu.addAction("Eliminar")

        global_pos = self.list.viewport().mapToGlobal(pos)
        act = menu.exec(global_pos)
        if not act:
            return

        if act == act_rename:
            self._rename_person(idx)
        elif act == act_pet:
            self._toggle_pet(idx)
        elif act == act_delete:
            self._delete_person(idx)

    # ─────────────────────── utilidades modelo ───────────────────────
    def _find_model_row_by_person_id(self, pid: str) -> int:
        for row in range(self.model.rowCount()):
            data = self.model.item(row).data(ROLE_DATA)
            if data and str(data.get("id")) == str(pid):
                return row
        return -1

    def _update_person_label(self, pid: str, _new_sug_count: int) -> None:
        row = self._find_model_row_by_person_id(pid)
        if row < 0:
            return
        it = self.model.item(row)
        data: Dict[str, Any] = it.data(ROLE_DATA) or {}
        title = (data.get("title") or "").strip() or "Agregar nombre"
        photos = int(data.get("photos", 0))
        it.setText(f"{title}\n{photos} foto{'s' if photos != 1 else ''}")

    def _refresh_person_icon(self, pid: str) -> None:
        if self.store is None:
            return
        row = self._find_model_row_by_person_id(pid)
        if row < 0:
            return
        it = self.model.item(row)
        data: Dict[str, Any] = it.data(ROLE_DATA) or {}
        try:
            persons = self.store.list_persons_overview()
            match = next((p for p in persons if str(
                p.get("id")) == str(pid)), None)
        except Exception:
            match = None
        cover = (match or {}).get("cover") or data.get("cover") or ""
        it.setIcon(QIcon(self._circular_pixmap(cover)))
        data["cover"] = cover
        it.setData(data, ROLE_DATA)

    def _apply_title_change(self, pid: str, new_title: str) -> None:
        row = self._find_model_row_by_person_id(pid)
        if row < 0:
            return
        it = self.model.item(row)
        data: Dict[str, Any] = it.data(ROLE_DATA) or {}
        data["title"] = new_title
        photos = int(data.get("photos", 0))
        base = (new_title or "").strip() or "Agregar nombre"
        it.setText(f"{base}\n{photos} foto{'s' if photos != 1 else ''}")
        it.setData(data, ROLE_DATA)

    def _rename_person(self, idx: QModelIndex) -> None:
        it = self.model.itemFromIndex(idx)
        data: Dict[str, Any] = it.data(ROLE_DATA) or {}
        old = (data.get("title") or "").strip()
        if not old:
            old = ""
        new, ok = QInputDialog.getText(self, "Asignar nombre", "", text=old)
        if not ok:
            return
        title = new.strip()
        if self.store:
            try:
                self.store.set_person_name(int(data["id"]), title or None)
            except Exception:
                pass
        data["title"] = title
        photos = int(data.get("photos", 0))
        base = title if title else "Agregar nombre"
        it.setText(f"{base}\n{photos} foto{'s' if photos != 1 else ''}")
        it.setData(data, ROLE_DATA)

    def _toggle_pet(self, idx: QModelIndex) -> None:
        it = self.model.itemFromIndex(idx)
        data: Dict[str, Any] = it.data(ROLE_DATA) or {}
        new_flag = not bool(data.get("is_pet"))
        if self.store:
            try:
                self.store.set_is_pet(int(data["id"]), new_flag)
            except Exception:
                pass
        data["is_pet"] = new_flag
        it.setData(data, ROLE_DATA)

    def _delete_person(self, idx: QModelIndex) -> None:
        it = self.model.itemFromIndex(idx)
        data: Dict[str, Any] = it.data(ROLE_DATA) or {}
        pid = data.get("id")
        if pid is None:
            return
        if self.store:
            try:
                self.store.delete_person(int(pid))
            except Exception:
                pass
        self.model.removeRow(idx.row())
        if self._current_person_id and str(pid) == str(self._current_person_id):
            self._go_back_to_list()

    # ────────────────────────── Mock ──────────────────────────
    def _mock_clusters(self) -> list[Dict[str, Any]]:
        out: list[Dict[str, Any]] = []
        for i in range(1, 9):
            out.append({
                "id": i,
                "title": "",
                "cover": "",
                "is_pet": False,
                "photos_count": 1,
                "suggestions_count": 0,
            })
        return out
