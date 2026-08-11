#!/usr/bin/env python3
"""Launcher for the 18:00 IG reel cron job (job 7a4c465fbd09).

Cron script-only jobs resolve relative paths under ~/.hermes/scripts/ and
REJECT absolute paths, but the real pipeline lives in the repo. This thin
shim chdirs into the repo and execs the real script so the cron tool only
ever sees a stable bare filename here.
"""
import os
import sys

REPO = "/root/Instagram daily auto-post"
TARGET = os.path.join(REPO, "scripts", "reel_post.py")

if not os.path.isfile(TARGET):
    sys.stderr.write(f"reel_post.py launcher: target missing: {TARGET}\n")
    sys.exit(4)

os.chdir(REPO)
os.execv(sys.executable, [sys.executable, TARGET] + sys.argv[1:])