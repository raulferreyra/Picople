from __future__ import annotations
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QStackedWidget,
    QStyle, QFrame, QMessageBox
)

from picople.infrastructure.db import Database
from .CollectionView import CollectionView


class PersonDetailView(QWidget):
    """
    Detalle de un “cluster” (persona o mascota).

    Header:
      [<]   [avatar circular]   [Título (SectionTitle)]    [✎ Renombrar]   [Sugerencias]

    Cuerpo:
      - Stacked: “Fotos” (placeholder por ahora) y “Sugerencias” (placeholder con acciones futuras).
      - Usamos CollectionView embebido sólo cuando conectemos filtro por cluster.
    """
    requestBack = Signal()

    def __init__(self, cluster: Dict[str, Any], db: Optional[Database], parent=None) -> None:
        super().__init__(parent)
        self.cluster = cluster
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ─────────── Header ───────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)

        # back
        self.btn_back = QToolButton()
        self.btn_back.setObjectName("ToolbarBtn")
        self.btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_back.clicked.connect(self.requestBack.emit)

        # avatar circular
        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)
        self._set_avatar_pixmap(self.cluster.get("cover"))

        # título
        self.lbl_title = QLabel(self.cluster.get("title") or "Sin nombre")
        self.lbl_title.setObjectName("SectionTitle")
        self.lbl_title.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # renombrar
        self.btn_rename = QToolButton()
        self.btn_rename.setObjectName("ToolbarBtn")
        self.btn_rename.setText("✎")
        self.btn_rename.setToolTip("Renombrar")
        self.btn_rename.clicked.connect(self._rename_cluster)

        # link “Sugerencias”
        self.btn_sug = QToolButton()
        self.btn_sug.setObjectName("ToolbarBtn")
        self.btn_sug.setText("Sugerencias")
        self.btn_sug.setToolTip("Ver/ocultar sugerencias para este rostro")
        self.btn_sug.setCheckable(True)
        self.btn_sug.toggled.connect(self._toggle_suggestions)

        hdr.addWidget(self.btn_back)
        hdr.addWidget(self.avatar)
        hdr.addWidget(self.lbl_title, 1)
        hdr.addWidget(self.btn_rename)
        hdr.addWidget(self.btn_sug)
        root.addLayout(hdr)

        # separador fino (coincide con SectionView)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("SectionSeparator")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # ─────────── Contenido ───────────
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        # Página “Fotos” (placeholder)
        self.page_photos = QWidget()
        lp = QVBoxLayout(self.page_photos)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.setSpacing(8)

        self.lbl_ph = QLabel("Aquí verás las fotos confirmadas de este rostro.\n"
                             "Aún no hay índice de caras, pronto lo conectaremos.")
        self.lbl_ph.setAlignment(Qt.AlignCenter)
        self.lbl_ph.setObjectName("SectionText")
        lp.addWidget(self.lbl_ph, 1)

        # (cuando exista filtro por cluster_id → usar CollectionView(embedded=True) con datasource por cluster)
        # self.coll = CollectionView(db=self.db, title="", subtitle="", embedded=True)
        # lp.addWidget(self.coll, 1)

        # Página “Sugerencias” (placeholder)
        self.page_sug = QWidget()
        ls = QVBoxLayout(self.page_sug)
        ls.setContentsMargins(0, 0, 0, 0)
        ls.setSpacing(8)

        self.lbl_sug = QLabel("Sugerencias para revisar:\n"
                              "• ✓ Confirmar que pertenece a este rostro\n"
                              "• ✗ Rechazar (mantenerá como desconocido)\n"
                              "• 🗑️ No es una cara (falso positivo)")
        self.lbl_sug.setAlignment(Qt.AlignCenter)
        self.lbl_sug.setObjectName("SectionText")
        ls.addWidget(self.lbl_sug, 1)

        self.pages.addWidget(self.page_photos)  # idx 0
        self.pages.addWidget(self.page_sug)     # idx 1
        self.pages.setCurrentIndex(0)

    # ───────────────── helpers ─────────────────
    def _set_avatar_pixmap(self, cover_path: Optional[str]) -> None:
        size = QSize(40, 40)
        if cover_path:
            pm = QPixmap(cover_path)
        else:
            # fallback: icono estándar
            sp = QStyle.SP_DialogYesButton if (self.cluster.get(
                "kind") == "person") else QStyle.SP_DriveDVDIcon
            pm = self.style().standardIcon(sp).pixmap(64, 64)

        if pm.isNull():
            self.avatar.clear()
            return

        # recorte circular
        pm = pm.scaled(size, Qt.KeepAspectRatioByExpanding,
                       Qt.SmoothTransformation)
        masked = QPixmap(size)
        masked.fill(Qt.transparent)
        p = QPainter(masked)
        p.setRenderHints(QPainter.Antialiasing |
                         QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addEllipse(0, 0, size.width(), size.height())
        p.setClipPath(path)
        # centrar recorte
        x = (pm.width() - size.width()) // 2
        y = (pm.height() - size.height()) // 2
        p.drawPixmap(-x, -y, pm)
        p.end()

        self.avatar.setPixmap(masked)

    def _toggle_suggestions(self, on: bool) -> None:
        self.pages.setCurrentIndex(1 if on else 0)

    def _rename_cluster(self) -> None:
        """
        Renombrar el cluster (opcional: si luego agregamos tabla clusters en DB).
        Por ahora solo mostramos aviso para no romper hasta tener el backend.
        """
        try:
            # Cuando exista: self.db.rename_person_cluster(self.cluster["id"], new_name)
            QMessageBox.information(self, "Personas y mascotas",
                                    "Renombrar estará disponible cuando activemos el índice de caras.")
        except Exception:
            pass
