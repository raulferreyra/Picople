# src/picople/infrastructure/people_avatars.py
from __future__ import annotations
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
from picople.core.log import log


class PeopleAvatarService:
    @staticmethod
    def _rect_from_bbox(img_w: int, img_h: int, x: float, y: float, w: float, h: float) -> Tuple[int, int, int, int]:
        normalized = (0 < w <= 2 and 0 < h <=
                      2 and 0 <= x <= 2 and 0 <= y <= 2)
        if normalized:
            px, py, pw, ph = int(
                round(x*img_w)), int(round(y*img_h)), int(round(w*img_w)), int(round(h*img_h))
        else:
            px, py, pw, ph = int(round(x)), int(
                round(y)), int(round(w)), int(round(h))
        px = max(0, min(px, img_w-1))
        py = max(0, min(py, img_h-1))
        pw = max(1, min(pw, img_w-px))
        ph = max(1, min(ph, img_h-py))
        return px, py, pw, ph

    @staticmethod
    def crop_face_square(src_path: str, bbox_xywh: Tuple[float, float, float, float], *, out_path: str,
                         out_size: int = 256, pad_ratio: float = 0.35) -> Optional[str]:
        p = Path(src_path)
        if not p.exists():
            log("PeopleAvatarService: src no existe:", src_path)
            return None
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                W, H = im.size
                x, y, w, h = PeopleAvatarService._rect_from_bbox(
                    W, H, *bbox_xywh)
                cx, cy = x + w/2.0, y + h/2.0
                side = int(round(max(w, h) * (1.0 + pad_ratio*2)))
                half = side // 2
                left, top = int(round(cx - half)), int(round(cy - half))
                right, bottom = left + side, top + side
                if left < 0:
                    right -= left
                    left = 0
                if top < 0:
                    bottom -= top
                    top = 0
                if right > W:
                    left -= (right-W)
                    right = W
                    left = max(0, left)
                if bottom > H:
                    top -= (bottom-H)
                    bottom = H
                    top = max(0, top)
                crop = im.crop((left, top, right, bottom)).resize(
                    (out_size, out_size), Image.LANCZOS)
                outp = Path(out_path)
                outp.parent.mkdir(parents=True, exist_ok=True)
                crop.save(outp, format="JPEG", quality=88)
                return str(outp)
        except Exception as e:
            log("PeopleAvatarService: error crop:", e, "src=", src_path)
            return None
