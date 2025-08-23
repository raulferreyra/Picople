from __future__ import annotations
from typing import List, Tuple

from PySide6.QtCore import QObject, Signal

from picople.core.log import log
from picople.infrastructure.db import Database
from picople.infrastructure.people_store import PeopleStore

# Detector pluggable (OpenCV si está disponible)
try:
    import cv2  # type: ignore
    _CV2_OK = True
except Exception:
    _CV2_OK = False


class FaceScanWorker(QObject):
    started = Signal(int)                # total previstos (aprox de lote)
    progress = Signal(int, int, str)     # i, total, path
    info = Signal(str)
    error = Signal(str, str)             # path, err
    finished = Signal(dict)              # summary

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.store = PeopleStore(db)
        self._cancel = False

        # Carga detector si hay OpenCV; si no, queda como no-op
        self._detector = None
        log("FaceScanWorker: OpenCV disponible:", _CV2_OK)
        if _CV2_OK:
            try:
                cascade_path = getattr(cv2.data, "haarcascades", "")
                cascade = cv2.CascadeClassifier(
                    cascade_path + "haarcascade_frontalface_default.xml"
                )
                if not cascade.empty():
                    self._detector = cascade
                    log("FaceScanWorker: cascade cargado OK")
                else:
                    log("FaceScanWorker: cascade vacío (no cargado)")
            except Exception as e:
                log("FaceScanWorker: error cargando cascade:", e)
                self._detector = None
        else:
            log("FaceScanWorker: OpenCV no disponible; detector desactivado")

    def cancel(self):
        self._cancel = True
        log("FaceScanWorker: cancel solicitado")

    def _detect_faces(self, img_path: str) -> List[Tuple[int, int, int, int]]:
        """
        Devuelve una lista de bboxes (x, y, w, h) en coordenadas de la imagen.
        Si no hay detector disponible, retorna [] (no rompe).
        """
        if not self._detector:
            return []
        import cv2  # type: ignore
        img = cv2.imread(img_path)
        if img is None:
            log("FaceScanWorker: no se pudo leer imagen:", img_path)
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self._detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(32, 32)
        )
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def run(self):
        """
        Escaneo incremental por lotes pequeños.
        - Toma medias no escaneadas (o con mtime más nuevo).
        - Detecta caras; inserta en faces; crea persona placeholder y sugerencia.
        - Marca media como escaneada.
        """
        if not _CV2_OK or self._detector is None:
            msg = "Caras: detector no disponible (OpenCV/cascade ausente)."
            log("FaceScanWorker.run:", msg)
            self.info.emit(msg)

        try:
            batch = self.store.get_unscanned_media(batch=48)
        except Exception as e:
            log("FaceScanWorker.run: error consultando lote:", e)
            self.error.emit("", f"Error consultando estado de escaneo: {e}")
            self.finished.emit({"scanned": 0, "faces": 0})
            return

        total = len(batch)
        log("FaceScanWorker.run: lote obtenido =", total)
        self.started.emit(total)
        if total == 0:
            msg = "Caras: no hay nuevas fotos/vídeos para analizar."
            log("FaceScanWorker.run:", msg)
            self.info.emit(msg)
            self.finished.emit({"scanned": 0, "faces": 0})
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
                boxes = self._detect_faces(path)
                log(f"FaceScanWorker.run: [{i}/{total}] caras detectadas =", len(boxes))
                for (x, y, w, h) in boxes:
                    q = float(w * h)  # calidad simple placeholder
                    face_id = self.store.add_face_by_media_id(
                        mid, (x, y, w, h), embedding=None, quality=q
                    )
                    pid = self.store.create_person(
                        display_name=None, is_pet=False, cover_path=thumb
                    )
                    self.store.add_suggestion(face_id, pid, score=q)
                    log(
                        f"FaceScanWorker: face_id={face_id} -> person_id={pid} (score={q})")

                faces_total += len(boxes)
                # marcar escaneado SIEMPRE (aunque no haya caras)
                self.store.mark_media_scanned(mid, item["mtime"])
                self.progress.emit(i, total, path)
            except Exception as e:
                log("FaceScanWorker.run: error en media:", path, "error:", e)
                self.error.emit(path, str(e))

        summary = {"scanned": total, "faces": faces_total}
        log("FaceScanWorker.run: terminado. summary=", summary)
        self.finished.emit(summary)
