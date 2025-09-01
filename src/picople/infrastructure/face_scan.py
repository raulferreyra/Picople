from __future__ import annotations
from typing import List, Tuple, Optional
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from picople.core.log import log
from picople.infrastructure.db import Database
from picople.infrastructure.people_store import PeopleStore

# Detector
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _CV2_OK = True
except Exception:
    _CV2_OK = False


def _cv_imread_unicode(path: str):
    try:
        data = np.fromfile(path, dtype=np.uint8)  # type: ignore
        return cv2.imdecode(data, cv2.IMREAD_COLOR)  # type: ignore
    except Exception:
        return None


class FaceScanWorker(QObject):
    started = Signal(int)
    progress = Signal(int, int, str)
    info = Signal(str)
    error = Signal(str, str)
    finished = Signal(dict)

    def __init__(self, db_path: str | Path, db_key: str):
        super().__init__()
        self.db_path = str(db_path)
        self.db_key = db_key
        self.db: Optional[Database] = None
        self.store: Optional[PeopleStore] = None
        self._cancel = False

        self._detector = None
        log("FaceScanWorker: OpenCV disponible:", _CV2_OK)
        if _CV2_OK:
            try:
                cascade = cv2.CascadeClassifier(getattr(cv2.data, "haarcascades", "") +
                                                "haarcascade_frontalface_default.xml")
                if not cascade.empty():
                    self._detector = cascade
                    log("FaceScanWorker: cascade cargado OK")
            except Exception as e:
                log("FaceScanWorker: error cargando cascade:", e)

    def cancel(self):
        self._cancel = True

    def _detect_faces(self, img_path: str) -> List[Tuple[int, int, int, int]]:
        if not self._detector:
            return []
        img = _cv_imread_unicode(img_path) if _CV2_OK else None
        if img is None:
            log("FaceScanWorker: no se pudo leer imagen:", img_path)
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # type: ignore
        faces = self._detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(32, 32))
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def run(self):
        # abrir DB en este hilo
        try:
            self.db = Database(Path(self.db_path))
            self.db.open(self.db_key)
            self.store = PeopleStore(self.db)
            log("FaceScanWorker.run: DB abierta en worker")
        except Exception as e:
            log("FaceScanWorker.run: no se pudo abrir DB en worker:", e)
            self.error.emit("", f"No se pudo abrir DB en worker: {e}")
            self.finished.emit({"scanned": 0, "faces": 0})
            return

        try:
            batch = self.store.get_unscanned_media(batch=48)
        except Exception as e:
            log("FaceScanWorker.run: error consultando lote:", e)
            self.error.emit("", f"Error consultando estado de escaneo: {e}")
            self.finished.emit({"scanned": 0, "faces": 0})
            self._close_db()
            return

        total = len(batch)
        self.started.emit(total)
        if total == 0:
            self.info.emit("Caras: no hay nuevas fotos/vídeos para analizar.")
            self.finished.emit({"scanned": 0, "faces": 0})
            self._close_db()
            return

        faces_total = 0
        for i, item in enumerate(batch, start=1):
            if self._cancel:
                break

            path = item["path"]
            mid = item["media_id"]
            thumb = item.get("thumb_path") or path

            try:
                boxes = self._detect_faces(path)
                for (x, y, w, h) in boxes:
                    q = float(w * h)
                    face_id = self.store.add_face_by_media_id(
                        mid, (x, y, w, h), embedding=None, quality=q)

                    # firma para agrupar
                    sig = self.store.compute_face_signature(
                        src_path=path, bbox_xywh=(x, y, w, h))
                    self.store.set_face_signature(face_id, sig)

                    # ¿persona existente?
                    pid = self.store.find_similar_person(
                        sig, max_hamming=10) if sig else None
                    if pid is None:
                        pid = self.store.create_person_from_face(face_id, sig)
                    else:
                        self.store.add_suggestion(face_id, pid, score=q)

                faces_total += len(boxes)
                self.store.mark_media_scanned(mid, item["mtime"])
                self.progress.emit(i, total, path)
            except Exception as e:
                self.error.emit(path, str(e))

        self.finished.emit({"scanned": total, "faces": faces_total})
        self._close_db()

    def _close_db(self):
        try:
            if self.db and getattr(self.db, "conn", None):
                self.db.conn.close()
        except Exception:
            pass
