# src/picople/core/log.py
from __future__ import annotations
import sys
from datetime import datetime

# Mapea algunos Unicode comunes a ASCII
_SAFE_MAP = str.maketrans({
    "→": "->",
    "←": "<-",
    "↔": "<->",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "—": "-",
    "–": "-",
})


def _timestamp() -> str:
    # [HH:MM:SS.mmm]
    return datetime.now().strftime("[%H:%M:%S.%f]")[:-3]


def log(*parts) -> None:
    try:
        msg = " ".join(str(p) for p in parts).translate(_SAFE_MAP)
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.buffer.write(_timestamp().encode(enc, errors="replace"))
        sys.stdout.buffer.write(b" ")
        sys.stdout.buffer.write(msg.encode(enc, errors="replace"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.flush()
    except Exception:
        # Último recurso: que no crashee jamás por loggear
        try:
            print(_timestamp(), *parts)
        except Exception:
            pass
