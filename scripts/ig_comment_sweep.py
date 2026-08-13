#!/usr/bin/env python3
"""Launcher for the IG comment sweep watchdog (called by cron).

Self-healing: locates the real scripts/comment_sweep.py even if the project
dir moved. Silent when the sweep has nothing to do; only emits output from
the underlying script.
"""
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ig_locate import locate_script

TARGET = locate_script("comment_sweep.py")
if not TARGET:
    sys.stderr.write(
        "ig_comment_sweep launcher: could not locate comment_sweep.py "
        "anywhere under /root\n"
    )
    sys.exit(2)

res = subprocess.run(
    ["python3", TARGET],
    capture_output=True,
    text=True,
)
sys.stdout.write(res.stdout or "")
sys.stdout.write(res.stderr or "")
sys.exit(res.returncode)
