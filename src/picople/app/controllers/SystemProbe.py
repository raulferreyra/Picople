from __future__ import annotations
import os
import shutil
import subprocess
import platform
from dataclasses import dataclass
from typing import List, Optional

try:
    import psutil  # type: ignore
except Exception:
    psutil = None


@dataclass
class ProbeResult:
    cpu_count: int
    ram_gb: Optional[int]
    os_name: str
    has_ffmpeg: bool
    heic_supported: bool
    onnx_providers: List[str]
    nvidia_name: Optional[str]
    suggested: dict


def _get_ram_gb() -> Optional[int]:
    try:
        if psutil:
            return int(psutil.virtual_memory().total / (1024**3))
    except Exception:
        pass
    return None


def _nvidia_name() -> Optional[str]:
    try:
        if shutil.which("nvidia-smi"):
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
            ).strip()
            return out.splitlines()[0] if out else "NVIDIA GPU"
    except Exception:
        pass
    return None


def _onnx_providers() -> List[str]:
    try:
        import onnxruntime as ort  # type: ignore
        return list(ort.get_available_providers())
    except Exception:
        return []


def _heic_supported() -> bool:
    try:
        import pillow_heif  # type: ignore
        return True
    except Exception:
        return False


def read_hardware() -> ProbeResult:
    cpu = os.cpu_count() or 1
    ram = _get_ram_gb()
    os_name = f"{platform.system()} {platform.release()}"
    has_ffmpeg = bool(shutil.which("ffmpeg"))
    providers = _onnx_providers()
    heic = _heic_supported()
    nvidia = _nvidia_name()

    # Heurística de sugerencias
    # (conservadora: ajustamos suavemente según CPU/RAM/GPU)
    if (ram or 0) >= 24 and cpu >= 8:
        collection_tile = 176
        batch = 300
        idx_thumb = 384
    elif (ram or 0) >= 12 and cpu >= 4:
        collection_tile = 160
        batch = 200
        idx_thumb = 352
    else:
        collection_tile = 144
        batch = 150
        idx_thumb = 320

    if "CUDAExecutionProvider" in providers:
        provider = "CUDA"
    elif "DmlExecutionProvider" in providers:
        provider = "DML"
    else:
        provider = "CPU"

    suggested = {
        "collection/tile_size": collection_tile,
        "collection/batch": batch,
        "indexer/thumb_size": idx_thumb,
        "indexer/video_thumbs": has_ffmpeg,  # activar si hay ffmpeg
        "ai/provider": provider,             # futuro (inferencia)
    }

    return ProbeResult(
        cpu_count=cpu,
        ram_gb=ram,
        os_name=os_name,
        has_ffmpeg=has_ffmpeg,
        heic_supported=heic,
        onnx_providers=providers,
        nvidia_name=nvidia,
        suggested=suggested,
    )
