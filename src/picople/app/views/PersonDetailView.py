from __future__ import annotations
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QStackedWidget,
    QStyle, QFrame, QMessageBox
)

from picople.infrastructure.db import Database
# from .CollectionView import CollectionView  # ← se activará cuando filtremos por cluster


class PersonDetailView(QWidget):
    """
    Detalle de un “cluster” (persona o mascota).

    Header:
      [<]   [avatar circular]   [Título (SectionTitle)]    [✎ Renombrar]   [Sugerencias]

    Cuerpo:
      - Stacked: “Fotos” y “Sugerencias” (placeholders hasta conectar DB/pipeline).
    """
    requestBack = Signal()

    def __init__(self, cluster: Dict[str, Any], db: Optional[Database], parent=None) -> None:
        super().__init__(parent)
        self.cluster = cluster
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ───────── Header ─────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)

        self.btn_back = QToolButton()
        self.btn_back.setObjectName("ToolbarBtn")
        self.btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_back.clicked.connect(self.requestBack.emit)

        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)
        self._set_avatar_pixmap(self.cluster.get("cover"))

        self.lbl_title = QLabel(self.cluster.get("title") or "Sin nombre")
        self.lbl_title.setObjectName("SectionTitle")
        self.lbl_title.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.btn_rename = QToolButton()
        self.btn_rename.setObjectName("ToolbarBtn")
        self.btn_rename.setText("✎")
        self.btn_rename.setToolTip("Renombrar")
        self.btn_rename.clicked.connect(self._rename_cluster)

        self.btn_sug = QToolButton()
        self.btn_sug.setObjectName("ToolbarBtn")
        self.btn_sug.setText("Sugerencias")
        self.btn_sug.setToolTip("Ver/ocultar sugerencias")
        self.btn_sug.setCheckable(True)
        self.btn_sug.toggled.connect(self._toggle_suggestions)

        hdr.addWidget(self.btn_back)
        hdr.addWidget(self.avatar)
        hdr.addWidget(self.lbl_title, 1)
        hdr.addWidget(self.btn_rename)
        hdr.addWidget(self.btn_sug)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("SectionSeparator")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # ───────── Contenido ─────────
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        # Fotos (placeholder)
        page_ph = QWidget()
        lp = QVBoxLayout(page_ph)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.setSpacing(8)
        lbl_ph = QLabel("Aquí verás las fotos confirmadas de este rostro.\n"
                        "Conectaremos el índice de caras en los siguientes pasos.")
        lbl_ph.setAlignment(Qt.AlignCenter)
        lbl_ph.setObjectName("SectionText")
        lp.addWidget(lbl_ph, 1)

        # (cuando exista filtro por cluster_id → usar CollectionView(embedded=True))
        # coll = CollectionView(db=self.db, title="", subtitle="", embedded=True)
        # lp.addWidget(coll, 1)

        # Sugerencias (placeholder)
        page_sg = QWidget()
        ls = QVBoxLayout(page_sg)
        ls.setContentsMargins(0, 0, 0, 0)
        ls.setSpacing(8)
        lbl_sg = QLabel("Sugerencias para revisar:\n"
                        "• ✓ Confirmar que pertenece a este rostro\n"
                        "• ✗ Rechazar (mantener como desconocido)\n"
                        "• 🗑️ No es una cara (falso positivo)")
        lbl_sg.setAlignment(Qt.AlignCenter)
        lbl_sg.setObjectName("SectionText")
        ls.addWidget(lbl_sg, 1)

        self.pages.addWidget(page_ph)  # 0
        self.pages.addWidget(page_sg)  # 1
        self.pages.setCurrentIndex(0)

    # ───────── helpers ─────────
    def _set_avatar_pixmap(self, cover_path: Optional[str]) -> None:
        size = QSize(40, 40)
        if cover_path:
            pm = QPixmap(cover_path)
        else:
            sp = QStyle.SP_DialogYesButton if (self.cluster.get(
                "kind") == "person") else QStyle.SP_DriveDVDIcon
            pm = self.style().standardIcon(sp).pixmap(64, 64)

        if pm.isNull():
            self.avatar.clear()
            return

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

        x = (pm.width() - size.width()) // 2
        y = (pm.height() - size.height()) // 2
        p.drawPixmap(-x, -y, pm)
        p.end()

        self.avatar.setPixmap(masked)

    def _toggle_suggestions(self, on: bool) -> None:
        self.pages.setCurrentIndex(1 if on else 0)

    def _rename_cluster(self) -> None:
        # Hook listo para cuando tengamos tabla de clusters.
        QMessageBox.information(
            self, "Personas y mascotas",
            "Renombrar estará disponible cuando activemos el índice de caras."
        )
