from __future__ import annotations
from typing import Tuple, Optional
from pathlib import Path

from PIL import Image, ImageOps


class PeopleAvatarService:
    @staticmethod
    def crop_face_square(src_path: str,
                         bbox_xywh: Tuple[float, float, float, float],
                         *, out_path: str,
                         out_size: int = 256,
                         pad_ratio: float = 0.25) -> Optional[str]:
        """
        Recorta la región del rostro (con padding) a un cuadrado out_size x out_size,
        respetando orientación EXIF. Devuelve la ruta del archivo generado.
        """
        try:
            im = Image.open(src_path)
            im = ImageOps.exif_transpose(im).convert("RGB")
            W, H = im.size
            x, y, w, h = bbox_xywh
            x = max(0, min(int(x), W - 1))
            y = max(0, min(int(y), H - 1))
            w = max(1, min(int(w), W - x))
            h = max(1, min(int(h), H - y))

            # expandir a cuadrado con padding
            cx, cy = x + w / 2.0, y + h / 2.0
            r = max(w, h) * (1.0 + pad_ratio) / 2.0
            left = int(max(0, cx - r))
            top = int(max(0, cy - r))
            right = int(min(W, cx + r))
            bottom = int(min(H, cy + r))

            crop = im.crop((left, top, right, bottom)).resize(
                (out_size, out_size), Image.LANCZOS)
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            crop.save(out_path, format="JPEG", quality=90)
            return out_path
        except Exception:
            return None
