from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QSpinBox, QCheckBox,
    QComboBox, QToolButton, QMessageBox
)
from PySide6.QtGui import QFontMetrics

from picople.app.controllers import SystemProbe, ProbeResult
from .SectionView import SectionView


class SettingsView(SectionView):
    """
    Preferencias: indexación, colección, IA; lectura de hardware y sugerencias.
    """
    settingsApplied = Signal(dict)  # emite diccionario de claves -> valores

    def __init__(self, settings: QSettings):
        super().__init__("Preferencias", "Ajusta recursos, miniaturas y rendimiento.", compact=True)
        self.settings = settings
        lay = self.layout()

        # ---- Hardware (lectura) ----
        self.lbl_hw = QLabel("Hardware: (sin leer)")
        self.lbl_hw.setObjectName("SectionText")
        self.btn_probe = QToolButton()
        self.btn_probe.setObjectName("ToolbarBtn")
        self.btn_probe.setText("Detectar hardware")
        self.btn_probe.clicked.connect(self._on_probe)

        row_hw = QHBoxLayout()
        row_hw.setSpacing(8)
        row_hw.addWidget(self.lbl_hw, 1)
        row_hw.addWidget(self.btn_probe)

        # ---- Indexación ----
        row_idx = QHBoxLayout()
        row_idx.setSpacing(8)
        self.sp_idx_thumb = QSpinBox()
        self.sp_idx_thumb.setRange(128, 768)
        self.sp_idx_thumb.setSingleStep(32)
        self.sp_idx_thumb.setValue(
            int(self.settings.value("indexer/thumb_size", 320)))
        self.cb_video_thumbs = QCheckBox("Miniaturas de video (ffmpeg)")
        self.cb_video_thumbs.setChecked(str(self.settings.value(
            "indexer/video_thumbs", "1")) in ("1", "true", "True"))

        row_idx.addWidget(QLabel("Miniatura indexación (px):"))
        row_idx.addWidget(self.sp_idx_thumb)
        row_idx.addSpacing(12)
        row_idx.addWidget(self.cb_video_thumbs)
        row_idx.addStretch(1)

        # ---- Colección ----
        row_coll = QHBoxLayout()
        row_coll.setSpacing(8)
        self.sp_tile = QSpinBox()
        self.sp_tile.setRange(128, 256)
        self.sp_tile.setSingleStep(8)
        self.sp_tile.setValue(
            int(self.settings.value("collection/tile_size", 160)))
        self.sp_batch = QSpinBox()
        self.sp_batch.setRange(50, 500)
        self.sp_batch.setSingleStep(50)
        self.sp_batch.setValue(
            int(self.settings.value("collection/batch", 200)))

        row_coll.addWidget(QLabel("Tamaño miniatura colección (px):"))
        row_coll.addWidget(self.sp_tile)
        row_coll.addSpacing(12)
        row_coll.addWidget(QLabel("Lote de carga (scroll):"))
        row_coll.addWidget(self.sp_batch)
        row_coll.addStretch(1)

        # ---- IA / Inferencia (futuro) ----
        row_ai = QHBoxLayout()
        row_ai.setSpacing(8)
        self.cmb_provider = QComboBox()
        self.cmb_provider.addItems(["Auto", "CPU", "DML", "CUDA"])
        self.cmb_provider.setCurrentText(
            str(self.settings.value("ai/provider", "Auto")))
        row_ai.addWidget(QLabel("Proveedor de inferencia (ONNX):"))
        row_ai.addWidget(self.cmb_provider)
        row_ai.addStretch(1)

        # ---- Botones ----
        row_btns = QHBoxLayout()
        row_btns.setSpacing(8)
        self.btn_suggest = QToolButton()
        self.btn_suggest.setObjectName("ToolbarBtn")
        self.btn_suggest.setText("Configuración sugerida")
        self.btn_apply = QToolButton()
        self.btn_apply.setObjectName("ToolbarBtn")
        self.btn_apply.setText("Aplicar")
        self.btn_save = QToolButton()
        self.btn_save.setObjectName("ToolbarBtn")
        self.btn_save.setText("Guardar")

        self.btn_suggest.clicked.connect(self._on_suggest)
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_save.clicked.connect(self._on_save)

        row_btns.addStretch(1)
        row_btns.addWidget(self.btn_suggest)
        row_btns.addWidget(self.btn_apply)
        row_btns.addWidget(self.btn_save)

        # ---- Montar ----
        lay.addLayout(row_hw)
        lay.addSpacing(6)
        lay.addLayout(row_idx)
        lay.addLayout(row_coll)
        lay.addLayout(row_ai)
        lay.addSpacing(8)
        lay.addLayout(row_btns)

        # Leer hardware al entrar (opcional)
        self._on_probe()

    # ---------- Slots ----------
    def _on_probe(self):
        pr: ProbeResult = SystemProbe.read()
        providers = ", ".join(
            pr.onnx_providers) if pr.onnx_providers else "N/D"
        gpu_name = pr.nvidia_name or (
            "DirectML" if "DmlExecutionProvider" in pr.onnx_providers else "—")
        txt = (
            f"SO: {pr.os_name}  •  CPU: {pr.cpu_count} hilos"
            + (f"  •  RAM: {pr.ram_gb} GB" if pr.ram_gb is not None else "")
            + f"\nGPU: {gpu_name}  •  onnxruntime: {providers}"
            + f"\nffmpeg: {'sí' if pr.has_ffmpeg else 'no'}  •  HEIC: {'sí' if pr.heic_supported else 'no'}"
        )
        self.lbl_hw.setText(txt)
        self._last_suggested = pr.suggested

    def _on_suggest(self):
        if not hasattr(self, "_last_suggested"):
            self._on_probe()
        sug = getattr(self, "_last_suggested", {})
        if not sug:
            QMessageBox.information(
                self, "Preferencias", "No se pudo generar sugerencia.")
            return
        self.sp_idx_thumb.setValue(
            int(sug.get("indexer/thumb_size", self.sp_idx_thumb.value())))
        self.cb_video_thumbs.setChecked(
            bool(sug.get("indexer/video_thumbs", self.cb_video_thumbs.isChecked())))
        self.sp_tile.setValue(
            int(sug.get("collection/tile_size", self.sp_tile.value())))
        self.sp_batch.setValue(
            int(sug.get("collection/batch", self.sp_batch.value())))
        prov = str(sug.get("ai/provider", self.cmb_provider.currentText()))
        if prov in ("Auto", "CPU", "DML", "CUDA"):
            self.cmb_provider.setCurrentText(prov)

    def _collect_settings(self) -> dict:
        return {
            "indexer/thumb_size": int(self.sp_idx_thumb.value()),
            "indexer/video_thumbs": bool(self.cb_video_thumbs.isChecked()),
            "collection/tile_size": int(self.sp_tile.value()),
            "collection/batch": int(self.sp_batch.value()),
            "ai/provider": str(self.cmb_provider.currentText()),
        }

    def _on_apply(self):
        cfg = self._collect_settings()
        self.settingsApplied.emit(cfg)

    def _on_save(self):
        cfg = self._collect_settings()
        for k, v in cfg.items():
            self.settings.setValue(k, v)
        self.settings.sync()
        self.settingsApplied.emit(cfg)
        QMessageBox.information(self, "Preferencias",
                                "Preferencias guardadas.")
