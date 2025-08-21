from __future__ import annotations
from typing import List, Optional
from .MediaItem import MediaItem


class MediaNavigator:
    def __init__(self, items: List[MediaItem], index: int = 0) -> None:
        self._items = items or []
        self._i = max(0, min(index, len(self._items) - 1)
                      ) if self._items else -1

    # estado
    def count(self) -> int:
        return len(self._items)

    @property
    def index(self) -> int:
        return self._i

    def current(self) -> Optional[MediaItem]:
        if 0 <= self._i < len(self._items):
            return self._items[self._i]
        return None

    # navegación
    def has_prev(self) -> bool:
        return self._i > 0

    def has_next(self) -> bool:
        return self._i + 1 < len(self._items)

    def prev(self) -> bool:
        if self.has_prev():
            self._i -= 1
            return True
        return False

    def next(self) -> bool:
        if self.has_next():
            self._i += 1
            return True
        return False
