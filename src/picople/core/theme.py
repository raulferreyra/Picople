# ─────────────────────────────────────────────────────────────────────────────
# File: src/picople/core/theme.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

# src/picople/core/theme.py

QSS_LIGHT = """
QMainWindow { background: #f7f9fc; color: #1f2937; }
QLabel#AppTitle { font-size: 18px; font-weight: 700; color: #111827; }

/* Sidebar */
#Sidebar { background: #ffffff; border-right: 1px solid #e5e7eb; }
QPushButton#NavButton {
    text-align: left;
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 10px;
    border: 1px solid transparent;
    background: transparent;
    color: #111827;
}
QPushButton#NavButton:hover { background: #eef2ff; border-color: #e5e7eb; }
QPushButton#NavButton:checked {
    background: #dbeafe; border-color: #93c5fd; font-weight: 600;
}

/* Toolbar */
QToolBar { background: #ffffff; border-bottom: 1px solid #e5e7eb; }
QToolButton#ToolbarBtn, QPushButton#ToolbarBtn {
    padding: 8px 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #ffffff;
    min-height: 30px;
    color: #111827;
}
QToolButton#ToolbarBtn:hover, QPushButton#ToolbarBtn:hover { background: #f3f4f6; }

/* Inputs */
QLineEdit#SearchEdit {
    padding: 8px 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    min-height: 30px;
    background: #ffffff;
    color: #111827;
}

/* Status bar */
QStatusBar { background: #ffffff; border-top: 1px solid #e5e7eb; }
QLabel#StatusTag { color: #374151; font-weight: 600; margin-right: 8px; }
QProgressBar { border: 1px solid #e5e7eb; border-radius: 8px; background: #f3f4f6; height: 16px; }
QProgressBar::chunk { background-color: #60a5fa; border-radius: 8px; }

/* Views (content) */
QLabel#SectionTitle { font-size: 20px; font-weight: 700; color: #0f172a; }
QLabel#SectionText  { font-size: 13px; color: #374151; }

/* Lists & grids (FoldersView) */
QListWidget {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QListWidget::item { color: #111827; }
QListWidget::item:selected {
    background: #e5efff;
    border-radius: 8px;
}
QComboBox#FilterCombo {
    padding: 6px 10px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #ffffff;
    color: #111827;
    min-height: 30px;
}
QComboBox#FilterCombo::drop-down { border: none; }
QToolButton#FilterBtn {
    padding: 8px 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #ffffff;
    color: #111827;
    min-height: 30px;
}
QToolButton#FilterBtn:hover { background: #f3f4f6; }

/* Grilla Collection (igual look que Folders) */
QListView {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QListView::item { color: #111827; }
QListView::item:selected {
    background: #e5efff;
    border-radius: 8px;
}
/* Status bar */
QStatusBar {
    background: #f9fafb;
    color: #111827;
    border-top: 1px solid #e5e7eb;
}
QStatusBar QLabel, QLabel#StatusLabel, QLabel#StatusTag { color: #111827; }

/* Color por defecto para etiquetas */
QLabel { color: #111827; }
#SectionSeparator { background: #e5e7eb; }
QToolBar#MainToolbar { border-bottom: 1px solid rgba(0,0,0,0.05); }
"""

QSS_DARK = """
QMainWindow { background: #0f172a; color: #e5e7eb; }
QLabel#AppTitle { font-size: 18px; font-weight: 700; color: #f9fafb; }

/* Sidebar */
#Sidebar { background: #0b1220; border-right: 1px solid #172036; }
QPushButton#NavButton {
    text-align: left;
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 10px;
    border: 1px solid transparent;
    background: transparent;
    color: #e5e7eb;
}
QPushButton#NavButton:hover { background: #162138; border-color: #1f2a44; }
QPushButton#NavButton:checked {
    background: #1f2a44; border-color: #334155; font-weight: 600;
}

/* Toolbar */
QToolBar { background: #0b1220; border-bottom: 1px solid #172036; }
QToolButton#ToolbarBtn, QPushButton#ToolbarBtn {
    padding: 8px 12px;
    border: 1px solid #172036;
    border-radius: 8px;
    background: #0b1220;
    min-height: 30px;
    color: #e5e7eb;
}
QToolButton#ToolbarBtn:hover, QPushButton#ToolbarBtn:hover { background: #101a2e; }

/* Inputs */
QLineEdit#SearchEdit {
    padding: 8px 12px;
    border: 1px solid #172036;
    border-radius: 8px;
    min-height: 30px;
    background: #0b1220;
    color: #f9fafb;
}

/* Status bar */
QStatusBar { background: #0b1220; border-top: 1px solid #172036; }
QLabel#StatusTag { color: #cbd5e1; font-weight: 600; margin-right: 8px; }
QProgressBar { border: 1px solid #172036; border-radius: 8px; background: #101a2e; height: 16px; }
QProgressBar::chunk { background-color: #60a5fa; border-radius: 8px; }

/* Views (content) */
QLabel#SectionTitle { font-size: 20px; font-weight: 700; color: #f8fafc; }
QLabel#SectionText  { font-size: 13px; color: #cbd5e1; }

/* Lists & grids (FoldersView) */
QListWidget {
    background: #0b1220;
    border: 1px solid #172036;
    border-radius: 8px;
}
QListWidget::item { color: #e5e7eb; }
QListWidget::item:selected {
    background: #1f2a44;
    border-radius: 8px;
}
QComboBox#FilterCombo {
    padding: 6px 10px;
    border: 1px solid #172036;
    border-radius: 8px;
    background: #0b1220;
    color: #e5e7eb;
    min-height: 30px;
}
QComboBox#FilterCombo::drop-down { border: none; }
QToolButton#FilterBtn {
    padding: 8px 12px;
    border: 1px solid #172036;
    border-radius: 8px;
    background: #0b1220;
    color: #e5e7eb;
    min-height: 30px;
}
QToolButton#FilterBtn:hover { background: #101a2e; }

/* Grilla Collection (igual look que Folders) */
QListView {
    background: #0b1220;
    border: 1px solid #172036;
    border-radius: 8px;
}
QListView::item { color: #e5e7eb; }
QListView::item:selected {
    background: #1f2a44;
    border-radius: 8px;
}
/* Status bar */
QStatusBar {
    background: #0a0f1a;
    color: #e5e7eb;
    border-top: 1px solid #172036;
}
QStatusBar QLabel, QLabel#StatusLabel, QLabel#StatusTag { color: #e5e7eb; }

/* Color por defecto para etiquetas */
QLabel { color: #e5e7eb; }
#SectionSeparator { background: #172036; }
QToolBar#MainToolbar { border-bottom: 1px solid #172036; }
"""
