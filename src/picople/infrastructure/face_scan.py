from __future__ import annotations
from typing import List, Tuple, Optional
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from picople.core.log import log
from picople.infrastructure.db import Database
from picople.infrastructure.people_store import PeopleStore

# Detector (OpenCV si disponible)
try:
    import cv2  # type: ignore
    _CV2_OK = True
except Exception:
    _CV2_OK = False

# Lectura robusta y EXIF
from PIL import Image, ImageOps
import numpy as np


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

        # Carga detector si hay OpenCV
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
        else:
            log("FaceScanWorker: OpenCV no disponible; detector desactivado")

    def cancel(self):
        self._cancel = True
        log("FaceScanWorker: cancel solicitado")

    # ---------- Lectura robusta (Pillow + EXIF) ----------
    def _read_image_rgb(self, path: str) -> Optional[np.ndarray]:
        try:
            im = Image.open(path)
            im = ImageOps.exif_transpose(im).convert("RGB")
            return np.array(im)  # RGB
        except Exception as e:
            log("FaceScanWorker: _read_image_rgb fallo:", path, e)
            return None

    # ---------- Hash perceptual simple (aHash 8x8) ----------
    def _ahash_hex_from_crop(self, img: Image.Image) -> str:
        g = img.convert("L").resize((8, 8), Image.LANCZOS)
        arr = np.array(g, dtype=np.float32)
        mean = float(arr.mean())
        bits = (arr > mean).flatten()
        val = 0
        for b in bits:
            val = (val << 1) | int(bool(b))
        return f"{val:016x}"

    def _detect_faces(self, img_path: str) -> List[Tuple[int, int, int, int]]:
        if not self._detector:
            return []
        rgb = self._read_image_rgb(img_path)
        if rgb is None:
            log("FaceScanWorker: no se pudo leer imagen:", img_path)
            return []

        # Downscale para acelerar (máx 1600px lado largo)
        h, w, _ = rgb.shape
        max_side = max(h, w)
        scale = 1.0
        if max_side > 1600:
            scale = 1600.0 / float(max_side)
            rgb_small = cv2.resize(
                rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
            )
        else:
            rgb_small = rgb

        gray = cv2.cvtColor(rgb_small, cv2.COLOR_RGB2GRAY)
        faces = self._detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(32, 32)
        )

        out: List[Tuple[int, int, int, int]] = []
        if scale != 1.0:
            inv = 1.0 / scale
            for (x, y, fw, fh) in faces:
                out.append((int(x * inv), int(y * inv),
                           int(fw * inv), int(fh * inv)))
        else:
            out = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
        return out

    def _face_sig_on_path(self, img_path: str, bbox_xywh: Tuple[int, int, int, int]) -> Optional[str]:
        try:
            im = Image.open(img_path)
            im = ImageOps.exif_transpose(im).convert("RGB")
        except Exception:
            return None

        W, H = im.size
        x, y, w, h = bbox_xywh
        x = max(0, min(x, W - 1))
        y = max(0, min(y, H - 1))
        w = max(1, min(w, W - x))
        h = max(1, min(h, H - y))
        crop = im.crop((x, y, x + w, y + h))
        try:
            return self._ahash_hex_from_crop(crop)
        except Exception:
            return None

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

        # 2) lote
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
            # coordenadas en la imagen usada
            detect_from = item.get("thumb_path") or path
            log(f"FaceScanWorker.run: [{i}/{total}] analizando", detect_from)

            try:
                boxes = self._detect_faces(detect_from)
                log(f"FaceScanWorker.run: [{i}/{total}] caras detectadas =", len(boxes))

                for (x, y, w, h) in boxes:
                    q = float(w * h)
                    # Guardamos bbox respecto a la imagen usada para detectar
                    face_id = self.store.add_face_by_media_id(
                        mid, (x, y, w, h), embedding=None, quality=q
                    )

                    # Firma para agrupar
                    sig = self._face_sig_on_path(detect_from, (x, y, w, h))
                    if sig:
                        try:
                            self.store.set_face_sig(face_id, sig)
                        except Exception as e:
                            log("FaceScanWorker: set_face_sig fallo:", e)

                    # Persona (agrupado por firma)
                    try:
                        pid = self.store.upsert_person_for_sig(
                            sig, cover_hint=None)
                    except Exception:
                        pid = self.store.create_person(
                            display_name=None, is_pet=False, cover_path=None, rep_sig=sig
                        )

                    # Sugerencia
                    try:
                        self.store.add_suggestion(face_id, pid, score=q)
                    except Exception as e:
                        log("FaceScanWorker: add_suggestion fallo:", e)

                    # Avatar/portada (recorte de rostro)
                    try:
                        avatar = self.store.make_avatar_from_face(
                            pid, face_id, out_size=256, pad_ratio=0.25
                        )
                        log(
                            "FaceScanWorker: avatar",
                            "OK" if avatar else "FAIL",
                            "pid=", pid,
                            "face=", face_id,
                            "->", avatar or "",
                        )
                    except Exception as e:
                        log("FaceScanWorker: make_avatar_from_face fallo:", e)

                faces_total += len(boxes)
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
