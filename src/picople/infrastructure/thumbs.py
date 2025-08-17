# src/picople/infrastructure/thumbs.py
from __future__ import annotations
import hashlib
import subprocess
import shutil
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

# HEIC/HEIF soporte (si está instalado)
try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()  # habilita PIL para abrir .heic/.heif
except Exception:
    pass


def _hash_for(path: Path) -> str:
    # Hash estable según ruta + tamaño + mtime (si cambia el archivo, cambia el hash)
    h = hashlib.sha1()
    p_bytes = str(path).encode("utf-8", errors="ignore")
    h.update(p_bytes)
    try:
        stat = path.stat()
        h.update(str(stat.st_size).encode())
        h.update(str(int(stat.st_mtime)).encode())
    except Exception:
        pass
    return h.hexdigest()


def image_thumb(src: Path, out_dir: Path, size: int = 320) -> Path:
    out = out_dir / f"{_hash_for(src)}.jpg"
    if out.exists():
        return out
    with Image.open(src) as im:
        # GIF animado → primer frame
        if getattr(im, "is_animated", False):
            im.seek(0)
        im = ImageOps.exif_transpose(im)  # respeta orientación
        # convertimos a RGB para JPG
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        # preservar aspecto
        im.thumbnail((size, size))
        bg = Image.new("RGB", (size, size), (16, 16, 16))
        # centrar
        x = (size - im.width) // 2
        y = (size - im.height) // 2
        bg.paste(im, (x, y))
        bg.save(out, format="JPEG", quality=85, optimize=True)
    return out


def video_thumb(src: Path, out_dir: Path, size: int = 320) -> Optional[Path]:
    # Requiere ffmpeg en PATH
    if not shutil.which("ffmpeg"):
        return None
    out = out_dir / f"{_hash_for(src)}.jpg"
    if out.exists():
        return out
    # Un frame representativo, escalado al tamaño manteniendo aspecto
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-frames:v", "1",
        "-vf", f"thumbnail,scale={size}:-1:flags=lanczos,pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x101010",
        str(out)
    ]
    subprocess.run(cmd, check=False)
    return out if out.exists() else None
