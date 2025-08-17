from __future__ import annotations
from typing import List, Optional
from .MediaItem import MediaItem


class MediaNavigator:
    def __init__(self, items: List[MediaItem], index: int = 0):
        self.items = items or []
        self.index = max(0, min(index, len(self.items) - 1))

    def current(self) -> Optional[MediaItem]:
        if not self.items:
            return None
        return self.items[self.index]

    def has_prev(self) -> bool:
        return self.index > 0

    def has_next(self) -> bool:
        return self.index < len(self.items) - 1

    def prev(self) -> Optional[MediaItem]:
        if self.has_prev():
            self.index -= 1
            return self.current()
        return None

    def next(self) -> Optional[MediaItem]:
        if self.has_next():
            self.index += 1
            return self.current()
        return None

    def goto(self, idx: int) -> Optional[MediaItem]:
        if 0 <= idx < len(self.items):
            self.index = idx
            return self.current()
        return None

    def count(self) -> int:
        return len(self.items)
