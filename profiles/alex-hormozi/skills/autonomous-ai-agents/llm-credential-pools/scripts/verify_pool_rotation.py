#!/usr/bin/env python3
"""Probe Hermes credential-pool rotation for a provider, in-process.

Drives the same load_pool() + select() path the aux clients use
(auxiliary_client._select_pool_entry). CLI chat probes do NOT touch
the pool for most providers -- use this instead.

Usage (from the hermes source dir, editable install):
  venv/bin/python verify_pool_rotation.py [provider] [n_selects]
"""
import sys

provider = sys.argv[1] if len(sys.argv) > 1 else "nvidia"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 6

from agent.credential_pool import load_pool, read_credential_pool

pool = load_pool(provider)
print(f"provider={provider} strategy={getattr(pool, '_strategy', '?')} "
      f"entries={[e.label for e in pool._entries]}")

picks = []
for _ in range(n):
    e = pool.select()
    picks.append(e.label if e else None)
print("picks:", " -> ".join(picks) if all(picks) else picks)

try:
    for entry in read_credential_pool(provider):
        print("persisted:", entry["label"],
              "priority=", entry.get("priority"),
              "source=", entry.get("source"),
              "request_count=", entry.get("request_count"))
except Exception as exc:
    print("read-back failed:", exc)