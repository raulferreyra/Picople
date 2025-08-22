# src/picople/app/event_bus.py
from __future__ import annotations
from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    # path del media, nuevo estado de favorito
    favoriteChanged = Signal(str, bool)


# Singleton simple para toda la app
bus = EventBus()
