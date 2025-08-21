from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional


Kind = Literal["image", "video"]


@dataclass(frozen=True, slots=True)
class MediaItem:
    path: str
    kind: Kind
    mtime: int
    size: int
    thumb_path: Optional[str] = None
    favorite: bool = False

    def is_image(self) -> bool:
        return self.kind == "image"

    def is_video(self) -> bool:
        return self.kind == "video"
