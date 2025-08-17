from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class ProbeResult:
    cpu_count: int
    ram_gb: Optional[int]
    os_name: str
    has_ffmpeg: bool
    heic_supported: bool
    onnx_providers: List[str]
    nvidia_name: Optional[str]
    suggested: Dict[str, object]
