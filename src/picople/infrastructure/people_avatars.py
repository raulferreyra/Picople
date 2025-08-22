from __future__ import annotations
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image


class PeopleAvatarService:
    """
    Servicio para generar avatares/portadas a partir de una cara (bbox) en una imagen.
    """

    @staticmethod
    def _rect_from_bbox(img_w: int, img_h: int, x: float, y: float, w: float, h: float) -> Tuple[int, int, int, int]:
        """
        Convierte bbox (x,y,w,h) a rectángulo en píxeles.
        Si los valores parecen normalizados (<=2), se escalan por el tamaño de la imagen.
        """
        normalized = (0 < w <= 2 and 0 < h <=
                      2 and 0 <= x <= 2 and 0 <= y <= 2)
        if normalized:
            px = int(round(x * img_w))
            py = int(round(y * img_h))
            pw = int(round(w * img_w))
            ph = int(round(h * img_h))
        else:
            px = int(round(x))
            py = int(round(y))
            pw = int(round(w))
            ph = int(round(h))

        # Limitar a imagen
        px = max(0, min(px, img_w - 1))
        py = max(0, min(py, img_h - 1))
        pw = max(1, min(pw, img_w - px))
        ph = max(1, min(ph, img_h - py))
        return px, py, pw, ph

    @staticmethod
    def crop_face_square(
        src_path: str,
        bbox_xywh: Tuple[float, float, float, float],
        *,
        out_path: str,
        out_size: int = 256,
        pad_ratio: float = 0.25,
    ) -> Optional[str]:
        """
        Genera un recorte cuadrado alrededor de la cara y lo guarda como JPEG.
        - src_path: imagen de origen (thumb o imagen completa)
        - bbox_xywh: (x,y,w,h) normalizado (0..1) o en píxeles
        - out_path: ruta destino .jpg
        - out_size: tamaño final del avatar
        - pad_ratio: margen alrededor de la cara (25% por defecto)
        Devuelve out_path si sale bien, None si falla.
        """
        p = Path(src_path)
        if not p.exists():
            return None

        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                W, H = im.size
                x, y, w, h = PeopleAvatarService._rect_from_bbox(
                    W, H, *bbox_xywh)

                # expandir a cuadrado con padding
                cx = x + w / 2.0
                cy = y + h / 2.0
                side = max(w, h)
                side = int(round(side * (1.0 + pad_ratio * 2)))
                half = side // 2

                left = int(round(cx - half))
                top = int(round(cy - half))
                right = left + side
                bottom = top + side

                # Clamp a bordes
                if left < 0:
                    right -= left
                    left = 0
                if top < 0:
                    bottom -= top
                    top = 0
                if right > W:
                    left -= (right - W)
                    right = W
                    left = max(0, left)
                if bottom > H:
                    top -= (bottom - H)
                    bottom = H
                    top = max(0, top)

                crop = im.crop((left, top, right, bottom))
                crop = crop.resize((out_size, out_size), Image.LANCZOS)

                outp = Path(out_path)
                outp.parent.mkdir(parents=True, exist_ok=True)
                crop.save(outp, format="JPEG", quality=88)
                return str(outp)
        except Exception:
            return None
