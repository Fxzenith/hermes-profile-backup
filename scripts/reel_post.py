#!/usr/bin/env python3
"""Launcher for the 18:00 IG reel cron job (job 7a4c465fbd09).

Self-healing: locates the real pipeline scripts/reel_post.py even if the
project dir moved. Falls back to a bounded recursive search under /root,
so a missing/renamed base dir can no longer break the job.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ig_locate import locate_script

TARGET = locate_script("reel_post.py")
if not TARGET:
    sys.stderr.write(
        "reel_post.py launcher: could not locate reel_post.py anywhere "
        "under /root\n"
    )
    sys.exit(4)

REPO = os.path.dirname(os.path.dirname(TARGET))
os.chdir(REPO)
os.execv(sys.executable, [sys.executable, TARGET] + sys.argv[1:])
