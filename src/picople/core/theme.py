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

/* Entradas */
QLineEdit#SearchBox {
    background: #151a22; border: 1px solid #1f2532; border-radius: 8px; padding: 8px 10px; color: #e6e6e6;
}

/* Botones del menú lateral */
QPushButton#MenuBtn {
    text-align: left; padding: 12px 16px; margin: 8px 12px; border-radius: 12px;
    color: #cfd6e4; background: transparent; border: 1px solid transparent;
}
QPushButton#MenuBtn:hover { background: #151a22; border-color: #202635; }
QPushButton#MenuBtn:pressed { background: #19202b; }

/* Título en la barra lateral */
QLabel#AppTitle { color: #e6e6e6; }

/* Botones de la toolbar (uniformes) */
QPushButton#ToolbarBtn {
    background: #1f6feb; color: #ffffff; border: none; border-radius: 8px; padding: 8px 14px; min-height: 30px;
}
QPushButton#ToolbarBtn:hover { background: #2b77ee; }
QPushButton#ToolbarBtn:pressed { background: #2568d1; }

/* Toggle de tema como QToolButton con solo ícono */
QToolButton#ThemeToggle {
    background: #151a22; color: #e6e6e6; border: 1px solid #1f2532; border-radius: 8px; padding: 6px 10px; min-height: 30px;
}
QToolButton#ThemeToggle:hover { background: #1a2130; }
QToolButton#ThemeToggle:checked { background: #1a2435; }

/* Barra de estado y progreso */
QStatusBar { background: #0b0d12; border-top: 1px solid #1e2530; }
QLabel#StatusLabel { color: #cfd6e4; }
QLabel#StatusTag { color: #9fb0c9; font-weight: 600; }
QProgressBar { background: #161b22; border: 1px solid #1e2530; border-radius: 6px; height: 14px; text-visible: false; }
QProgressBar::chunk { background-color: #1f6feb; border-radius: 6px; }

/* Contenido placeholder */
QLabel#WelcomeLabel { color: #cfd6e4; }
"""

QSS_LIGHT = """
* { font-family: Segoe UI, Roboto, Arial; font-size: 13px; }
QMainWindow { background: #f7f9fc; color: #1d2127; }
QFrame#Sidebar { background: #ffffff; border-right: 1px solid #e2e8f0; }
QFrame#Content { background: #f7f9fc; }
QToolBar { background: #ffffff; border-bottom: 1px solid #e2e8f0; }

/* Entradas */
QLineEdit#SearchBox {
    background: #ffffff; border: 1px solid #d1d9e6; border-radius: 8px; padding: 8px 10px; color: #1d2127;
}

/* Botones del menú lateral */
QPushButton#MenuBtn {
    text-align: left; padding: 12px 16px; margin: 8px 12px; border-radius: 12px;
    color: #1d2127; background: transparent; border: 1px solid transparent;
}
QPushButton#MenuBtn:hover { background: #eef3fb; border-color: #d1d9e6; }
QPushButton#MenuBtn:pressed { background: #e5eefb; }

/* Título en la barra lateral */
QLabel#AppTitle { color: #1d2127; }

/* Botones de la toolbar (uniformes) */
QPushButton#ToolbarBtn {
    background: #2563eb; color: #ffffff; border: none; border-radius: 8px; padding: 8px 14px; min-height: 30px;
}
QPushButton#ToolbarBtn:hover { background: #2b6df0; }
QPushButton#ToolbarBtn:pressed { background: #1f56c5; }

/* Toggle de tema como QToolButton con solo ícono */
QToolButton#ThemeToggle {
    background: #ffffff; color: #1d2127; border: 1px solid #d1d9e6; border-radius: 8px; padding: 6px 10px; min-height: 30px;
}
QToolButton#ThemeToggle:hover { background: #eef3fb; }
QToolButton#ThemeToggle:checked { background: #e5eefb; }

/* Barra de estado y progreso */
QStatusBar { background: #ffffff; border-top: 1px solid #e2e8f0; }
QLabel#StatusLabel { color: #475569; }
QLabel#StatusTag { color: #475569; font-weight: 600; }
QProgressBar { background: #eef3fb; border: 1px solid #d1d9e6; border-radius: 6px; height: 14px; text-visible: false; }
QProgressBar::chunk { background-color: #2563eb; border-radius: 6px; }

/* Contenido placeholder */
QLabel#WelcomeLabel { color: #475569; }
"""
