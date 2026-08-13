#!/usr/bin/env python3
"""Shared IG pipeline locator with self-healing path resolution.

Cron launchers used to hardcode /root/Instagram daily auto-post and broke
the moment the project moved. This resolves the real script/scripts/<name>
by: (1) trying known candidate base dirs, then (2) a bounded recursive
find under /root. Returns an absolute path or None -- never raises.
"""
import os
import subprocess

# Base dirs to check first, in priority order.
CANDIDATE_BASES = [
    "/root/projects/Instagram daily auto-post",
    "/root/Instagram daily auto-post",
    os.path.expanduser("~/Instagram daily auto-post"),
    "/root/projects",
    "/root",
]


def locate_script(name):
    """Return absolute path to <name> inside a scripts/ dir, else None."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    here_parent = os.path.dirname(script_dir)

    candidates = [os.path.join(here_parent, "Instagram daily auto-post")]
    candidates += CANDIDATE_BASES
    seen = set()
    for base in candidates:
        base = os.path.expanduser(base)
        if base in seen:
            continue
        seen.add(base)
        p = os.path.join(base, "scripts", name)
        if os.path.isfile(p):
            return os.path.abspath(p)

    # Fallback: bounded recursive search under /root.
    try:
        out = subprocess.run(
            ["find", "/root", "-name", name, "-type", "f",
             "-not", "-path", "*/.*/*", "-not", "-path", "*/__pycache__/*"],
            capture_output=True, text=True, timeout=30,
        )
        for line in out.stdout.splitlines():
            line = line.strip()
            if "/scripts/" in line and os.path.isfile(line):
                return os.path.abspath(line)
    except Exception:
        pass
    return None


if __name__ == "__main__":
    import sys
    for n in sys.argv[1:] or ("reel_post.py", "comment_sweep.py"):
        print(f"{n}: {locate_script(n)}")
