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
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (src.stem + ".jpg")

        im = Image.open(src)
        im = ImageOps.exif_transpose(im)  # respeta EXIF
        im.thumbnail((size, size), Image.Resampling.LANCZOS)

        # fondo oscuro neutro
        bg = Image.new("RGB", (size, size), (16, 16, 20))
        # centrar manteniendo aspecto
        x = (size - im.width)//2
        y = (size - im.height)//2
        bg.paste(im, (x, y))
        bg.save(out, "JPEG", quality=90)
        return out
    except Exception:
        return None


def video_thumb(src: Path, out_dir: Path, size: int = 320) -> Optional[Path]:
    if not shutil.which("ffmpeg"):
        return None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (src.stem + ".jpg")

        # Frame temprano pero no negro: 0.5s
        # Escalado cuadrado manteniendo aspecto + padding
        vf = f"scale='iw*min({size}/iw\\,{size}/ih)':'ih*min({size}/iw\\,{size}/ih)',pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x101418"

        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-ss", "0.5",
            "-i", str(src),
            "-frames:v", "1",
            "-vf", vf,
            "-y",
            str(out)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        return out if out.exists() else None
    except Exception:
        # intento de fallback (seek después de -i por exactitud)
        try:
            vf = f"scale='iw*min({size}/iw\\,{size}/ih)':'ih*min({size}/iw\\,{size}/ih)',pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x101418"
            cmd = [
                "ffmpeg",
                "-hide_banner", "-loglevel", "error",
                "-i", str(src),
                "-ss", "0.5",
                "-frames:v", "1",
                "-vf", vf,
                "-y",
                str(out)
            ]
            subprocess.run(
                cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return out if out.exists() else None
        except Exception:
            return None
