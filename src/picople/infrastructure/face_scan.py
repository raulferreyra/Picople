from __future__ import annotations
from typing import List, Tuple, Optional
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from picople.core.log import log
from picople.infrastructure.db import Database
from picople.infrastructure.people_store import PeopleStore

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _CV2_OK = True
except Exception:
    _CV2_OK = False


def _imread_unicode(path: str):
    """
    cv2.imread a veces falla con rutas Unicode en Windows. Esta variante usa
    np.fromfile + imdecode.
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)  # type: ignore
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)  # type: ignore
    except Exception:
        return None


def _ahash_hex(img_gray_roi) -> Optional[str]:
    """
    Average hash (8x8 → 64 bits) en hex. ROI ya en escala de grises.
    """
    try:
        small = cv2.resize(img_gray_roi, (8, 8),
                           interpolation=cv2.INTER_AREA)  # type: ignore
        m = small.mean()
        bits = (small > m).astype(np.uint8).flatten()  # type: ignore
        val = 0
        for b in bits:
            val = (val << 1) | int(b)
        return f"{val:016x}"
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
                cascade_path = getattr(cv2.data, "haarcascades", "")
                cascade = cv2.CascadeClassifier(
                    cascade_path + "haarcascade_frontalface_default.xml")  # type: ignore
                if not cascade.empty():
                    self._detector = cascade
                    log("FaceScanWorker: cascade cargado OK")
                else:
                    log("FaceScanWorker: cascade vacío (no cargado)")
            except Exception as e:
                log("FaceScanWorker: error cargando cascade:", e)
        else:
            log("FaceScanWorker: OpenCV no disponible; detector desactivado")

    def cancel(self):
        self._cancel = True
        log("FaceScanWorker: cancel solicitado")

    def _detect_faces(self, img_bgr) -> List[Tuple[int, int, int, int]]:
        if not self._detector or img_bgr is None:
            return []
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)  # type: ignore
        faces = self._detector.detectMultiScale(
            gray, scaleFactor=1.08, minNeighbors=5, minSize=(32, 32))
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces], gray

    def run(self):
        # 1) abrir DB en el hilo del worker
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
        log("FaceScanWorker.run: lote obtenido =", total)
        self.started.emit(total)
        if total == 0:
            msg = "Caras: no hay nuevas fotos/vídeos para analizar."
            log("FaceScanWorker.run:", msg)
            self.info.emit(msg)
            self.finished.emit({"scanned": 0, "faces": 0})
            self._close_db()
            return

        faces_total = 0
        for i, item in enumerate(batch, start=1):
            if self._cancel:
                log("FaceScanWorker.run: cancelado en iter", i)
                break

            path = item["path"]
            mid = item["media_id"]
            thumb = item.get("thumb_path") or path
            log(f"FaceScanWorker.run: [{i}/{total}] analizando", path)

            try:
                img = _imread_unicode(path) if _CV2_OK else None
                if img is None:
                    log("FaceScanWorker: no se pudo leer imagen:", path)
                    self.store.mark_media_scanned(mid, item["mtime"])
                    self.progress.emit(i, total, path)
                    continue

                boxes, gray = self._detect_faces(img)
                log(f"FaceScanWorker.run: [{i}/{total}] caras detectadas =", len(boxes))

                boxes = self._detect_faces(path)
                for (x, y, w, h) in boxes:
                    q = float(w * h)
                    face_id = self.store.add_face_by_media_id(
                        mid, (x, y, w, h), embedding=None, quality=q
                    )

                    # Persona sin nombre (sin cover inicial)
                    pid = self.store.create_person(
                        display_name=None, is_pet=False, cover_path=None)

                    # Sugerencia a esa persona
                    self.store.add_suggestion(face_id, pid, score=q)

                    # ✨ Generar avatar recortado desde el bbox y dejarlo como cover
                    try:
                        self.store.make_avatar_from_face(pid, face_id)
                    except Exception:
                        pass

                faces_total += len(boxes)
                # marcar media como escaneada
                self.store.mark_media_scanned(mid, item["mtime"])
                self.progress.emit(i, total, path)
            except Exception as e:
                log("FaceScanWorker.run: error en media:", path, "error:", e)
                self.error.emit(path, str(e))

        summary = {"scanned": total, "faces": faces_total}
        log("FaceScanWorker.run: terminado. summary=", summary)
        self.finished.emit(summary)
        self._close_db()

    def _close_db(self):
        try:
            if self.db and getattr(self.db, "conn", None):
                self.db.conn.close()
                log("FaceScanWorker.run: DB cerrada en worker")
        except Exception as e:
            log("FaceScanWorker.run: error cerrando DB:", e)
