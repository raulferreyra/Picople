from __future__ import annotations
from typing import Tuple, Optional
from pathlib import Path

from PIL import Image

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
                         pad_ratio: float = 0.25) -> Optional[str]:
        """
        Recorta un cuadrado centrado en la cara (bbox) con padding y lo guarda
        como JPEG en out_path. Devuelve out_path o None si falla.
        """
        try:
            im = Image.open(src_path).convert("RGB")
        except Exception:
            return None

        W, H = im.size
        x, y, w, h = bbox_xywh
        # centro y lado con padding
        cx = x + w * 0.5
        cy = y + h * 0.5
        side = max(w, h) * (1.0 + pad_ratio * 2.0)

        # coordenadas iniciales
        left = int(round(cx - side * 0.5))
        top = int(round(cy - side * 0.5))
        right = int(round(cx + side * 0.5))
        bottom = int(round(cy + side * 0.5))

        # clamp a bordes
        left = max(0, left)
        top = max(0, top)
        right = min(W, right)
        bottom = min(H, bottom)

        # asegurar cuadrado
        crop_w = right - left
        crop_h = bottom - top
        if crop_w != crop_h:
            if crop_w > crop_h:
                # expandir vertical si hay espacio
                extra = crop_w - crop_h
                top = max(0, top - extra // 2)
                bottom = min(H, top + crop_w)
            else:
                extra = crop_h - crop_w
                left = max(0, left - extra // 2)
                right = min(W, left + crop_h)

        # validación final
        if right <= left or bottom <= top:
            return None

        face = im.crop((left, top, right, bottom))
        face = face.resize((out_size, out_size), Image.LANCZOS)

        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        try:
            face.save(out_p, format="JPEG", quality=92, optimize=True)
        except Exception:
            return None
        return str(out_p)
