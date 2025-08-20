# src/picople/infrastructure/indexer.py
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from picople.core.formats import IMAGE_EXTS, VIDEO_EXTS
from picople.core.paths import thumbs_dir
from picople.infrastructure.thumbs import image_thumb, video_thumb
from picople.infrastructure.db import Database
from picople.core.log import log


class IndexerWorker(QObject):
    started = Signal(int)                 # total archivos
    progress = Signal(int, int, str)      # indexed, total, path
    info = Signal(str)                    # mensajes informativos
    error = Signal(str, str)              # path, error
    finished = Signal(dict)               # resumen

    def __init__(
        self,
        roots: List[str],
        thumb_size: int = 320,
        *,
        db_path: Optional[Path] = None,
        db_key: Optional[str] = None,
        allow_video_thumbs: bool = True
    ) -> None:
        super().__init__()
        self.roots = [Path(r) for r in roots if r]
        self.thumb_size = thumb_size
        self.db_path = Path(db_path) if db_path else None
        self.db_key = db_key
        self.allow_video_thumbs = allow_video_thumbs
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True
        log("Indexer: cancel() solicitado")

    def _collect_files(self) -> List[Path]:
        files: List[Path] = []
        seen: set[str] = set()
        for root in self.roots:
            if not root.exists():
                msg = f"Carpeta no existe: {root}"
                self.info.emit(msg)
                log("Indexer._collect_files:", msg)
                continue
            log("Indexer._collect_files: escaneando raíz:", str(root))
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    p = Path(dirpath) / fn
                    ext = p.suffix.lower()
                    if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
                        key = str(p.resolve())
                        if key not in seen:
                            files.append(p)
                            seen.add(key)
            log("Indexer._collect_files: raíz lista:",
                str(root), "acumulados:", len(files))
        log("Indexer._collect_files: total encontrados:", len(files))
        return files

    def run(self) -> None:
        local_db: Optional[Database] = None
        try:
            log("Indexer.run: inicio", {
                "roots": [str(r) for r in self.roots],
                "thumb_size": self.thumb_size,
                "allow_video_thumbs": self.allow_video_thumbs,
                "db_path": str(self.db_path) if self.db_path else None,
                "has_key": bool(self.db_key),
            })

            # Abrimos una conexión PROPIA en este hilo (si hay credenciales)
            if self.db_path and self.db_key:
                try:
                    local_db = Database(self.db_path)
                    local_db.open(self.db_key)
                    log("Indexer.run: DB abierta en hilo de indexación")
                except Exception as e:
                    log("Indexer.run: ERROR abriendo DB:", e)
                    self.error.emit("(db-open)", str(e))
                    local_db = None

            files = self._collect_files()
            total = len(files)
            self.started.emit(total)
            if total == 0:
                log("Indexer.run: no hay archivos que indexar")
                self.finished.emit(
                    {"total": 0, "images": 0, "videos": 0, "thumbs_ok": 0, "thumbs_fail": 0})
                return

            thumbs = thumbs_dir()
            counts = {"total": total, "images": 0,
                      "videos": 0, "thumbs_ok": 0, "thumbs_fail": 0}

            for i, p in enumerate(files, start=1):
                if self._cancel:
                    self.info.emit("Indexación cancelada.")
                    log("Indexer.run: cancelado por el usuario en",
                        f"{i-1}/{total}")
                    break
                try:
                    ext = p.suffix.lower()
                    st = p.stat()
                    mtime = int(st.st_mtime)
                    size = int(st.st_size)
                    kind = "image" if ext in IMAGE_EXTS else "video"

                    log(f"Indexer[{i}/{total}]: procesando",
                        {"kind": kind, "path": str(p)})

                    thumb_file = None
                    if kind == "image":
                        counts["images"] += 1
                        out = image_thumb(p, thumbs, self.thumb_size)
                        thumb_file = str(out) if out and out.exists() else None
                        if thumb_file:
                            counts["thumbs_ok"] += 1
                            log("Indexer: thumb imagen OK →", thumb_file)
                        else:
                            counts["thumbs_fail"] += 1
                            log("Indexer: thumb imagen FAIL")
                    else:
                        counts["videos"] += 1
                        if self.allow_video_thumbs:
                            log("Indexer: generando thumb de video…", str(p))
                            out = video_thumb(p, thumbs, self.thumb_size)
                            thumb_file = str(
                                out) if out and out.exists() else None
                            if thumb_file:
                                counts["thumbs_ok"] += 1
                                log("Indexer: thumb video OK →", thumb_file)
                            else:
                                counts["thumbs_fail"] += 1
                                log("Indexer: thumb video FAIL")
                        else:
                            log("Indexer: thumbs de video deshabilitados")

                    if local_db and local_db.is_open:
                        local_db.upsert_media(
                            str(p), kind, mtime, size, thumb_file)
                        # Nota: si necesitas auditar, descomenta esta línea:
                        # log("Indexer: DB upsert:", {"path": str(p), "kind": kind, "thumb": thumb_file is not None})

                except Exception as e:
                    self.error.emit(str(p), str(e))
                    counts["thumbs_fail"] += 1
                    log("Indexer.ERROR:", str(p), "|", e)
                finally:
                    self.progress.emit(i, total, str(p))

            log("Indexer.run: terminado con resumen:", counts)
            self.finished.emit(counts)

        except Exception as e:
            self.error.emit("(indexer)", str(e))
            log("Indexer.run: EXCEPCIÓN toplevel:", e)
            self.finished.emit(
                {"total": 0, "images": 0, "videos": 0, "thumbs_ok": 0, "thumbs_fail": 0})
        finally:
            try:
                if local_db:
                    local_db.close()
                    log("Indexer.run: DB cerrada")
            except Exception:
                pass
