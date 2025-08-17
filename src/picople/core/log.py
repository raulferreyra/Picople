from __future__ import annotations
import sys
import datetime


def log(*args):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}]", *args, file=sys.stdout, flush=True)
