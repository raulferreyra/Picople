# src/picople/infrastructure/indexer.py
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from PySide6.QtCore import QObject, Signal

from picople.core.formats import IMAGE_EXTS, VIDEO_EXTS
from picople.core.paths import thumbs_dir
from picople.infrastructure.thumbs import image_thumb, video_thumb
from picople.infrastructure.db import Database


class IndexerWorker(QObject):
    started = Signal(int)                             # total archivos
    progress = Signal(int, int, str)                  # indexed, total, path
    info = Signal(str)                                # mensajes informativos
    error = Signal(str, str)                          # path, error
    finished = Signal(dict)                           # resumen

    def __init__(self, roots: List[str], thumb_size: int = 320) -> None:
        super().__init__()
        self.roots = [Path(r) for r in roots if r]
        self.thumb_size = thumb_size
        self.db = db

    def _collect_files(self) -> List[Path]:
        files: List[Path] = []
        seen: set[str] = set()
        for root in self.roots:
            if not root.exists():
                self.info.emit(f"Carpeta no existe: {root}")
                continue
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    p = Path(dirpath) / fn
                    ext = p.suffix.lower()
                    if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
                        key = str(p.resolve())
                        if key not in seen:
                            files.append(p)
                            seen.add(key)
        return files

    def run(self) -> None:
        try:
            files = self._collect_files()
            total = len(files)
            self.started.emit(total)
            if total == 0:
                self.finished.emit(
                    {"total": 0, "images": 0, "videos": 0, "thumbs_ok": 0, "thumbs_fail": 0})
                return

            thumbs = thumbs_dir()
            counts = {"total": total, "images": 0,
                      "videos": 0, "thumbs_ok": 0, "thumbs_fail": 0}

            for i, p in enumerate(files, start=1):
                try:
                    ext = p.suffix.lower()
                    st = p.stat()
                    mtime = int(st.st_mtime)
                    size = int(st.st_size)
                    kind = "image" if ext in IMAGE_EXTS else "video"

                    thumb_file = None
                    if ext in IMAGE_EXTS:
                        counts["images"] += 1
                        out = image_thumb(p, thumbs, self.thumb_size)
                        thumb_file = str(out) if out and out.exists() else None
                        counts["thumbs_ok" if thumb_file else "thumbs_fail"] += 1
                    else:
                        counts["videos"] += 1
                        out = video_thumb(p, thumbs, self.thumb_size)
                        thumb_file = str(out) if out and out.exists() else None
                        counts["thumbs_ok" if thumb_file else "thumbs_fail"] += 1

                    # Persistir en DB (si está disponible)
                    if self.db and self.db.is_open:
                        self.db.upsert_media(
                            str(p), kind, mtime, size, thumb_file)

                except Exception as e:
                    self.error.emit(str(p), str(e))
                    counts["thumbs_fail"] += 1
                finally:
                    self.progress.emit(i, total, str(p))

            self.finished.emit(counts)
        except Exception as e:
            self.error.emit("(indexer)", str(e))
            self.finished.emit(
                {"total": 0, "images": 0, "videos": 0, "thumbs_ok": 0, "thumbs_fail": 0})
