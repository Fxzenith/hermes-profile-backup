#!/usr/bin/env python3
"""Verify a reel/story frame or MP4 has pure-black margins.

Usage:
    python3 verify_pure_black.py <frame.png|frame.jpg>
    python3 verify_pure_black.py <reel.mp4>          # decodes a frame first

Exits 0 only if top/bottom 100px and left/right 40px strips are all (0,0,0)
in the sampled frame. For MP4 input, decodes one frame at t=2s via ffmpeg
and checks that — the pixels IG actually displays, H.264 rounding included.

The foreground card region is NOT checked: margins only. NP hardening: keep
the frame PNG so JPEG noise can't lift blacks.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def check_path(path: Path) -> bool:
    img = np.array(Image.open(path).convert("RGB"))
    ok = True
    for name in ("top", "bottom", "left", "right"):
        if name == "top":
            region = img[:100, :, :]
        elif name == "bottom":
            region = img[-100:, :, :]
        elif name == "left":
            region = img[:, :80, :]
        else:
            region = img[:, -80:, :]
        px = region.reshape(-1, 3)
        maxv = int(px.max())
        found = bool(np.any(px != 0))
        print(f"{name:6s}: max={maxv} non-black px={int(found)}/{len(px)}")
        if found:
            ok = False
    return ok


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    if src.suffix.lower() == ".mp4":
        with tempfile.TemporaryDirectory() as td:
            frame = Path(td) / "frame.png"
            r = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", "2",
                 "-i", str(src), "-frames:v", "1", str(frame)],
                capture_output=True, text=True)
            if r.returncode != 0:
                print(f"ffmpeg decode failed: {r.stderr[-400:]}")
                return 1
            ok = check_path(frame)
    else:
        ok = check_path(src)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())