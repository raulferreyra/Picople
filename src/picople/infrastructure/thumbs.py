# src/picople/infrastructure/thumbs.py
from __future__ import annotations
import hashlib
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from picople.core.log import log

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
        log("thumbs.video: ffmpeg no encontrado")
        return None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (src.stem + ".jpg")

        base_vf = f"scale='iw*min({size}/iw\\,{size}/ih)':'ih*min({size}/iw\\,{size}/ih)',pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x101418"

        attempts = [
            ("thumbnail",
             ["-hide_banner", "-loglevel", "error", "-i", str(src),
              "-vf", f"thumbnail,{base_vf}",
              "-frames:v", "1", "-y", str(out)]),
            ("ss_after",
             ["-hide_banner", "-loglevel", "error", "-i", str(src), "-ss", "3.0",
              "-vf", base_vf, "-frames:v", "1", "-y", str(out)]),
            ("ss_before",
             ["-hide_banner", "-loglevel", "error", "-ss", "2.0", "-i", str(src),
              "-vf", base_vf, "-frames:v", "1", "-y", str(out)]),
        ]

        for name, cmd in attempts:
            log(f"thumbs.video: try {name} → {src}")
            try:
                subprocess.run(
                    cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if out.exists() and out.stat().st_size > 0:
                    log(f"thumbs.video: success {name} → {out}")
                    return out
            except Exception as e:
                log(f"thumbs.video: fail {name} → {e}")

        log("thumbs.video: all attempts failed", src)
        return None
    except Exception as e:
        log("thumbs.video: EXC", e)
        return None
