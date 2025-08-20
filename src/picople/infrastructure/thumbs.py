# src/picople/infrastructure/thumbs.py
from __future__ import annotations
import hashlib
import subprocess
import shutil
import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps
from picople.core.log import log

# HEIC/HEIF soporte (si está instalado)
try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()  # habilita PIL para abrir .heic/.heif
except Exception:
    pass

# FFmpeg vía imageio-ffmpeg (binario embebido en el paquete)
try:
    from imageio_ffmpeg import get_ffmpeg_exe  # type: ignore
except Exception:
    get_ffmpeg_exe = None  # fallback si no está instalado


def _hash_for(path: Path) -> str:
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


def _resolve_ffmpeg_path() -> Optional[str]:
    # 1) imageio-ffmpeg
    if get_ffmpeg_exe is not None:
        try:
            exe = get_ffmpeg_exe()
            if exe and Path(exe).exists():
                log(f"thumbs: ffmpeg via imageio-ffmpeg -> {exe}")
                return exe
        except Exception as e:
            log(f"thumbs: imageio-ffmpeg get_ffmpeg_exe error: {e}")

    # 2) assets/ffmpeg/ffmpeg(.exe)
    proj_root = Path(__file__).resolve().parents[2]  # .../src/picople/...
    candidate = proj_root / "assets" / "ffmpeg" / \
        ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if candidate.exists():
        log(f"thumbs: ffmpeg via assets -> {candidate}")
        return str(candidate)

    # 3) PATH
    found = shutil.which("ffmpeg")
    if found:
        log(f"thumbs: ffmpeg via PATH -> {found}")
        return found

    return None


def image_thumb(src: Path, out_dir: Path, size: int = 320) -> Optional[Path]:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (src.stem + ".jpg")

        im = Image.open(src)
        im = ImageOps.exif_transpose(im)  # respeta EXIF
        im.thumbnail((size, size), Image.Resampling.LANCZOS)

        # fondo oscuro neutro
        bg = Image.new("RGB", (size, size), (16, 16, 20))
        # centrar manteniendo aspecto
        x = (size - im.width) // 2
        y = (size - im.height) // 2
        bg.paste(im, (x, y))
        bg.save(out, "JPEG", quality=90)
        return out
    except Exception as e:
        log(f"thumbs.image: EXC {e} @ {src}")
        return None


def video_thumb(src: Path, out_dir: Path, size: int = 320) -> Optional[Path]:
    ffmpeg = _resolve_ffmpeg_path()
    if not ffmpeg:
        log("thumbs.video: ffmpeg no encontrado (imageio-ffmpeg/assets/PATH)")
        return None

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (src.stem + ".jpg")

        base_vf = (
            f"scale='iw*min({size}/iw\\,{size}/ih)':'ih*min({size}/iw\\,{size}/ih)',"
            f"pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x101418"
        )

        attempts = [
            # toma un frame “representativo”
            ("thumbnail", [
                ffmpeg, "-hide_banner", "-loglevel", "error",
                "-i", str(src),
                "-vf", f"thumbnail,{base_vf}",
                "-frames:v", "1", "-y", str(out)
            ]),
            # seek después de -i (preciso)
            ("ss_after", [
                ffmpeg, "-hide_banner", "-loglevel", "error",
                "-i", str(src),
                "-ss", "3.0",
                "-vf", base_vf, "-frames:v", "1", "-y", str(out)
            ]),
            # seek antes de -i (rápido)
            ("ss_before", [
                ffmpeg, "-hide_banner", "-loglevel", "error",
                "-ss", "2.0", "-i", str(src),
                "-vf", base_vf, "-frames:v", "1", "-y", str(out)
            ]),
        ]

        for name, cmd in attempts:
            log(f"thumbs.video: try {name} -> {src}")
            try:
                subprocess.run(
                    cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if out.exists() and out.stat().st_size > 0:
                    log(f"thumbs.video: success {name} -> {out}")
                    return out
            except Exception as e:
                log(f"thumbs.video: fail {name} -> {e}")

        log(f"thumbs.video: all attempts failed -> {src}")
        return None

    except Exception as e:
        log(f"thumbs.video: EXC {e} @ {src}")
        return None
