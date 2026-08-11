# External assets (not in this repo)

Things a full VPS reset needs beyond `~/.hermes`. Restore these separately.

- `/root/gbrain` — second brain (PGLite DB at `~/.gbrain/brain.pglite`, bun CLI, NVIDIA embeddings, Latitude telemetry env)
- `/root/autoclipping` — YouTube Shorts autoclipper pipeline (Node + Python scripts)
- REELS pipeline — cron `7a4c465fbd09` (18:00 reel): `scripts/reel_post.py`, `music/` (11 user tracks), pipeline `.env` with PIXABAY_API_KEY; 11:00 image post via `composio_post.py`
- `~/.venvs/*` — Python venvs (PEP 668; `pip` needs a venv)
- `~/.agentmail/` — AgentMail credentials (`phemeloagent-001@agentmail.to`)
- `/root/.bun`, `/root/.local/bin/latitude` — CLI tools (reinstallable)
- `~/.ssh/` — SSH keys (user's public key lives on Windows at `C:\Users\phemelo\.ssh\id_ed25519\id_ed25519.pub`)
