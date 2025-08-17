from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class MediaItem:
    path: str
    kind: str             # "image" | "video"
    mtime: int
    size: int
    thumb_path: Optional[str] = None
