# ─────────────────────────────────────────────────────────────────────────────
# File: src/picople/core/theme.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

QSS_DARK = """
* { font-family: Segoe UI, Roboto, Arial; font-size: 13px; }
QMainWindow { background: #0f1115; color: #e6e6e6; }
QFrame#Sidebar { background: #0b0d12; border-right: 1px solid #1e2530; }
QFrame#Content { background: #0f1115; }
QToolBar { background: #0b0d12; border-bottom: 1px solid #1e2530; }
QLineEdit#SearchBox {
    background: #151a22; border: 1px solid #1f2532; border-radius: 8px; padding: 8px 10px; color: #e6e6e6;
}
QPushButton#MenuBtn { text-align: left; padding: 10px 14px; margin: 4px 8px; border-radius: 10px;
    color: #cfd6e4; background: transparent; border: 1px solid transparent; }
QPushButton#MenuBtn:hover { background: #151a22; border-color: #202635; }
QPushButton#MenuBtn:pressed { background: #19202b; }
QPushButton#PrimaryBtn { background: #1f6feb; color: white; border: none; border-radius: 8px; padding: 8px 14px; }
QPushButton#PrimaryBtn:hover { background: #2b77ee; }
QPushButton#PrimaryBtn:pressed { background: #2568d1; }
QStatusBar { background: #0b0d12; border-top: 1px solid #1e2530; }
QProgressBar { background: #161b22; border: 1px solid #1e2530; border-radius: 6px; height: 14px; text-visible: false; }
QProgressBar::chunk { background-color: #1f6feb; border-radius: 6px; }
QLabel#StatusLabel { color: #cfd6e4; }
"""

QSS_LIGHT = """
* { font-family: Segoe UI, Roboto, Arial; font-size: 13px; }
QMainWindow { background: #f7f9fc; color: #1d2127; }
QFrame#Sidebar { background: #ffffff; border-right: 1px solid #e2e8f0; }
QFrame#Content { background: #f7f9fc; }
QToolBar { background: #ffffff; border-bottom: 1px solid #e2e8f0; }
QLineEdit#SearchBox {
    background: #ffffff; border: 1px solid #d1d9e6; border-radius: 8px; padding: 8px 10px; color: #1d2127;
}
QPushButton#MenuBtn { text-align: left; padding: 10px 14px; margin: 4px 8px; border-radius: 10px;
    color: #1d2127; background: transparent; border: 1px solid transparent; }
QPushButton#MenuBtn:hover { background: #eef3fb; border-color: #d1d9e6; }
QPushButton#MenuBtn:pressed { background: #e5eefb; }
QPushButton#PrimaryBtn { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 8px 14px; }
QPushButton#PrimaryBtn:hover { background: #2b6df0; }
QPushButton#PrimaryBtn:pressed { background: #1f56c5; }
QStatusBar { background: #ffffff; border-top: 1px solid #e2e8f0; }
QProgressBar { background: #eef3fb; border: 1px solid #d1d9e6; border-radius: 6px; height: 14px; text-visible: false; }
QProgressBar::chunk { background-color: #2563eb; border-radius: 6px; }
QLabel#StatusLabel { color: #475569; }
"""
