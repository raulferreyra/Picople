# infrastructure/face_scan.py
from __future__ import annotations
from typing import List, Tuple

from PySide6.QtCore import QObject, Signal

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
        if _CV2_OK:
            try:
                cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                if not cascade.empty():
                    self._detector = cascade
            except Exception:
                self._detector = None

    def cancel(self):
        self._cancel = True

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
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self._detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(32, 32))
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def run(self):
        """
        Escaneo incremental por lotes pequeños.
        - Toma medias no escaneadas (o con mtime más nuevo).
        - Detecta caras; inserta en faces; crea persona placeholder y sugerencia.
        - Marca media como escaneada.
        """
        try:
            batch = self.store.get_unscanned_media(batch=48)
        except Exception as e:
            self.error.emit("", f"Error consultando estado de escaneo: {e}")
            self.finished.emit({"scanned": 0, "faces": 0})
            return

        total = len(batch)
        self.started.emit(total)
        faces_total = 0

        for i, item in enumerate(batch, start=1):
            if self._cancel:
                break
            path = item["path"]
            mid = item["media_id"]
            thumb = item.get("thumb_path") or path
            try:
                boxes = self._detect_faces(path)
                # crea una persona placeholder por cada cara detectada
                for (x, y, w, h) in boxes:
                    # calidad simple (área del bbox como placeholder)
                    q = float(w * h)
                    face_id = self.store.add_face(path, (x, y, w, h),
                                                  embedding=None, quality=q)
                    if face_id is None:
                        continue
                    # persona sin nombre + sugerencia hacia esa persona
                    pid = self.store.create_person(
                        display_name=None, is_pet=False, cover_path=thumb)
                    self.store.add_suggestion(face_id, pid, score=q)
                faces_total += len(boxes)
                # marcar escaneado
                self.store.mark_media_scanned(mid, item["mtime"])
                self.progress.emit(i, total, path)
            except Exception as e:
                self.error.emit(path, str(e))

        self.finished.emit({"scanned": total, "faces": faces_total})
