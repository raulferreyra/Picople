# app/views/PersonDetailView.py
from __future__ import annotations
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QStackedWidget,
    QScrollArea, QGridLayout, QFrame, QInputDialog, QMenu
)

from picople.infrastructure.people_store import PeopleStore
from .SuggestionTile import SuggestionTile

TILE = 160


class PersonDetailView(QWidget):
    """
    Detalle de persona/mascota.
    Header:
      [Avatar 40x40]  Título  [✎]  [⋮ menú]
      [Links: Todos | Sugerencias (N)]
    """
    suggestionCountChanged = Signal(int)
    titleChanged = Signal(str)
    coverChanged = Signal()  # para refrescar ícono en la lista

    def __init__(
        self,
        cluster: Optional[Dict[str, Any]] = None,     # modo mock
        *,
        store: Optional[PeopleStore] = None,          # modo DB
        person_id: Optional[int] = None,
        person_title: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.cluster = cluster
        self.store = store
        self.person_id = person_id
        self.person_title = person_title or (
            cluster.get("title") if cluster else "Sin nombre")

        self._sugs: List[Dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # Header
        hdr = QVBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self.lbl_avatar = QLabel(self)
        self.lbl_avatar.setFixedSize(40, 40)
        self._set_avatar((cluster or {}).get("cover") if cluster else None)

        self.lbl_title = QLabel(self.person_title, self)
        self.lbl_title.setObjectName("SectionTitle")

        self.btn_rename = QToolButton(self)
        self.btn_rename.setObjectName("ToolbarBtn")
        self.btn_rename.setText("✎")
        self.btn_rename.setToolTip("Renombrar")
        self.btn_rename.clicked.connect(self._rename)

        self.btn_menu = QToolButton(self)
        self.btn_menu.setObjectName("ToolbarBtn")
        self.btn_menu.setText("⋮")
        self.btn_menu.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.btn_menu)
        act_regen = QAction("Regenerar avatar (auto)", self)
        menu.addAction(act_regen)
        self.btn_menu.setMenu(menu)
        act_regen.triggered.connect(self._regen_avatar)

        top.addWidget(self.lbl_avatar)
        top.addWidget(self.lbl_title, 1)
        top.addWidget(self.btn_rename)
        top.addWidget(self.btn_menu)

        links = QHBoxLayout()
        links.setContentsMargins(0, 0, 0, 0)
        links.setSpacing(12)

        self.btn_all = QToolButton(self)
        self.btn_all.setObjectName("ToolbarBtn")
        self.btn_all.setText("Todos")
        self.btn_all.clicked.connect(self.show_all)

        self.btn_sugs = QToolButton(self)
        self.btn_sugs.setObjectName("ToolbarBtn")
        self.btn_sugs.clicked.connect(self.show_suggestions)

        links.addWidget(self.btn_all)
        links.addWidget(self.btn_sugs)
        links.addStretch(1)

        hdr.addLayout(top)
        hdr.addLayout(links)
        root.addLayout(hdr)

        # Contenido
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 1)

        # Página “Todos”
        self.page_all = QWidget(self)
        la = QVBoxLayout(self.page_all)
        la.setContentsMargins(0, 0, 0, 0)
        la.setSpacing(0)

        self.scroll_all = QScrollArea(self.page_all)
        self.scroll_all.setWidgetResizable(True)
        self.scroll_all.setFrameShape(QFrame.NoFrame)
        self._all_host = QWidget(self.scroll_all)
        self._grid_all = QGridLayout(self._all_host)
        self._grid_all.setContentsMargins(0, 0, 0, 0)
        self._grid_all.setHorizontalSpacing(12)
        self._grid_all.setVerticalSpacing(12)
        self.scroll_all.setWidget(self._all_host)
        la.addWidget(self.scroll_all, 1)

        self.stack.addWidget(self.page_all)

        # Página “Sugerencias”
        self.page_sugs = QWidget(self)
        ls = QVBoxLayout(self.page_sugs)
        ls.setContentsMargins(0, 0, 0, 0)
        ls.setSpacing(0)

        self.scroll = QScrollArea(self.page_sugs)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_host = QWidget(self.scroll)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)

        self.scroll.setWidget(self.grid_host)
        ls.addWidget(self.scroll, 1)
        self.stack.addWidget(self.page_sugs)

        # Estado inicial
        self._load_all()
        self._load_suggestions()
        self.show_all()

    # Estado páginas
    def is_on_suggestions(self) -> bool:
        return self.stack.currentWidget() is self.page_sugs

    # Header helpers
    def _set_avatar(self, cover_path: Optional[str]):
        size = 40
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(QRect(0, 0, size, size))
        painter.setClipPath(path)

        if cover_path:
            src = QPixmap(cover_path)
            if not src.isNull():
                src = src.scaled(
                    size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap(0, 0, src)
            else:
                painter.fillRect(0, 0, size, size, Qt.gray)
        else:
            painter.fillRect(0, 0, size, size, Qt.gray)

        painter.end()
        self.lbl_avatar.setPixmap(pm)

    def _update_sug_link_text(self):
        n = len(self._sugs)
        self.btn_sugs.setText(f"Sugerencias ({n})")
        self.suggestionCountChanged.emit(n)

    def set_title(self, new_title: str) -> None:
        self.person_title = new_title or "Sin nombre"
        self.lbl_title.setText(self.person_title)

    # Páginas
    def show_all(self):
        self.stack.setCurrentWidget(self.page_all)
        self.btn_all.setEnabled(False)
        self.btn_sugs.setEnabled(True)

    def show_suggestions(self):
        self.stack.setCurrentWidget(self.page_sugs)
        self.btn_all.setEnabled(True)
        self.btn_sugs.setEnabled(False)

    # Renombrar
    def _rename(self):
        old = self.person_title or "Sin nombre"
        new, ok = QInputDialog.getText(
            self, "Renombrar persona/mascota", "", text=old)
        if not ok:
            return
        title = new.strip()
        if not title or title == old:
            return

        if self.store and self.person_id is not None:
            try:
                self.store.set_person_name(self.person_id, title)
            except Exception:
                pass
        elif self.cluster is not None:
            self.cluster["title"] = title

        self.set_title(title)
        self.titleChanged.emit(title)

    # Avatar
    def _regen_avatar(self):
        if not (self.store and self.person_id is not None):
            return
        try:
            path = self.store.generate_cover_for_person(
                self.person_id)  # asumido existente en tu store
            if path:
                self._set_avatar(path)
                self.coverChanged.emit()
        except Exception:
            pass

    # Carga “Todos”
    def _load_all(self):
        # limpiar
        while self._grid_all.count():
            item = self._grid_all.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        thumbs: List[str] = []
        if self.store and self.person_id is not None:
            media = self.store.list_person_media(
                self.person_id, limit=400, offset=0)
            thumbs = [m.get("thumb_path") or m.get("path") for m in media]
        else:
            thumbs = []

        if not thumbs:
            ph = QLabel(
                "Aquí iría la grilla de fotos/videos del cluster (pendiente).", self.page_all)
            ph.setObjectName("SectionText")
            self._grid_all.addWidget(ph, 0, 0)
            return

        cols = max(1, self.width() // (TILE + 12))
        size = 140
        for i, tp in enumerate(thumbs):
            lab = QLabel()
            lab.setFixedSize(size, size)
            lab.setAlignment(Qt.AlignCenter)
            pm = QPixmap(tp)
            if pm.isNull():
                pm = QPixmap(size, size)
                pm.fill(Qt.darkGray)
            lab.setPixmap(
                pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lab.setStyleSheet(
                "background: rgba(255,255,255,0.06); border-radius: 6px;")
            r = i // cols
            c = i % cols
            self._grid_all.addWidget(lab, r, c)

    # Carga “Sugerencias”
    def _load_suggestions(self):
        # limpiar grid y lista
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._sugs = []

        if self.store and self.person_id is not None:
            rows = self.store.list_person_suggestions(
                self.person_id, limit=400, offset=0)
            self._sugs = [
                {"id": str(r["face_id"]), "thumb": r["thumb"]} for r in rows]
        elif self.cluster:
            self._sugs = list(self.cluster.get("suggestions", []))

        cols = max(1, self.width() // (TILE + 16))
        for i, sug in enumerate(self._sugs):
            tile = SuggestionTile(sug_id=str(
                sug["id"]), thumb_path=sug.get("thumb"))
            tile.acceptClicked.connect(self._on_accept)
            tile.rejectClicked.connect(self._on_reject)
            tile.discardClicked.connect(self._on_discard)  # ← ocultar rostro
            tile.coverClicked.connect(self._on_set_cover)
            r = i // cols
            c = i % cols
            self.grid.addWidget(tile, r, c)

        self._update_sug_link_text()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._load_all()
        if self.stack.currentWidget() is self.page_sugs:
            self._load_suggestions()

    # Acciones Sugerencia
    def _remove_sug_by_id(self, sug_id: str):
        self._sugs = [s for s in self._sugs if str(s.get("id")) != str(sug_id)]
        self._load_suggestions()

    def _on_accept(self, sug_id: str):
        if self.store and self.person_id is not None:
            try:
                self.store.accept_suggestion(int(sug_id), self.person_id)
            except Exception:
                pass
        self._remove_sug_by_id(sug_id)

    def _on_reject(self, sug_id: str):
        if self.store and self.person_id is not None:
            try:
                self.store.reject_suggestion(int(sug_id), self.person_id)
            except Exception:
                pass
        self._remove_sug_by_id(sug_id)

    def _on_discard(self, sug_id: str):
        """
        Ocultar rostro (no borrar):
        - Marca la cara como escondida (faces.is_hidden=1).
        - La cara deja de aparecer en list_person_suggestions (ya filtramos is_hidden=0).
        """
        if self.store:
            try:
                self.store.hide_face(int(sug_id), True)
            except Exception:
                pass
        self._remove_sug_by_id(sug_id)

    def _on_set_cover(self, sug_id: str):
        if not (self.store and self.person_id is not None):
            return
        try:
            path = self.store.set_person_cover_from_face(
                self.person_id, int(sug_id))  # asumido existente en tu store
            if path:
                self._set_avatar(path)
                self.coverChanged.emit()
        except Exception:
            pass
