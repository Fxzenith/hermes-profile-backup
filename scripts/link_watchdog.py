#!/usr/bin/env python3
"""Silent-on-success link watchdog. Non-empty stdout = alert."""
import subprocess, sys, socket
try:
    s = socket.create_connection(('127.0.0.1', 27183), timeout=4); s.close()
except Exception:
    print("🔴 VPS↔local Hermes link DOWN: TCP 127.0.0.1:27183 unreachable "
          "(tunnel or Windows serve dead — watchdog should self-heal; "
          "run `python3 /root/local_hermes_doctor.py` if it persists >15 min)")
    sys.exit(0)
r = subprocess.run([sys.executable, '/root/local_hermes_doctor.py'],
                   capture_output=True, text=True, timeout=60)
if r.returncode != 0:
    print("🔴 VPS↔local Hermes link DEGRADED:\n" + r.stdout)
sys.exit(0)
