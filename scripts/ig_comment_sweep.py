#!/usr/bin/env python3
"""Launcher for the IG comment sweep watchdog (called by cron).
Runs the real sweep script in the project dir; silent when idle.
"""
import subprocess
import sys

res = subprocess.run(
    ["python3", "/root/Instagram daily auto-post/scripts/comment_sweep.py"],
    capture_output=True,
    text=True,
)
sys.stdout.write(res.stdout or "")
sys.stdout.write(res.stderr or "")
sys.exit(res.returncode)