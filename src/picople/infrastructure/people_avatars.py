from __future__ import annotations
from typing import Tuple, Optional
from pathlib import Path

# No importes cv2 si no está; lo cargamos perezoso:
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _CV2_OK = True
except Exception:
    _CV2_OK = False


def _imread_unicode(path: str):
    """
    cv2.imread falla con rutas Unicode en Windows; usamos fromfile + imdecode.
    """
    if not _CV2_OK:
        return None
    try:
        data = np.fromfile(path, dtype=np.uint8)  # type: ignore
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)  # type: ignore
    except Exception:
        return None


class PeopleAvatarService:
    @staticmethod
    def crop_face_square(src_path: str,
                         bbox_xywh: Tuple[float, float, float, float],
                         *,
                         out_path: str,
                         out_size: int = 256,
                         pad_ratio: float = 0.35) -> Optional[str]:
        """
        Crea un avatar cuadrado (zoom) a partir del rostro detectado.
        - src_path: thumb o foto original
        - bbox_xywh: coordenadas del rostro (en píxeles absolutos)
        - out_path: ruta de salida (se crean carpetas)
        - pad_ratio: margen adicional proporcional al lado mayor del rostro
        """
        if not _CV2_OK:
            return None

        img = _imread_unicode(src_path)
        if img is None:
            return None

        h_img, w_img = img.shape[:2]
        x, y, w, h = bbox_xywh
        # ROI base
        cx = x + w / 2.0
        cy = y + h / 2.0
        side = max(w, h) * (1.0 + pad_ratio)

        # Cuadrado centrado en el rostro con padding
        x0 = int(max(0, cx - side / 2.0))
        y0 = int(max(0, cy - side / 2.0))
        x1 = int(min(w_img, cx + side / 2.0))
        y1 = int(min(h_img, cy + side / 2.0))

        if x1 <= x0 or y1 <= y0:
            return None

        face = img[y0:y1, x0:x1]
        if face.size == 0:
            return None

        # A 256x256
        face = cv2.resize(face, (out_size, out_size),
                          interpolation=cv2.INTER_AREA)  # type: ignore

        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # JPG de salida (calidad 92)
        try:
            cv2.imencode(".jpg", face, [int(cv2.IMWRITE_JPEG_QUALITY), 92])[
                1].tofile(str(out_p))  # type: ignore
        except Exception:
            return None

        return str(out_p)
