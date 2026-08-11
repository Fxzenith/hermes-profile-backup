Python is PEP 668 externally-managed: pip needs a venv (~/.venvs/<name>) or pipx/uv.
§
User stores knowledge/notes in a gbrain second brain (repo /root/gbrain, PGLite DB at ~/.gbrain/brain.pglite, bun CLI v0.42.59.0, NVIDIA 2048-dim embeddings). Browser/web_search often fails auth on this box, and new sessions default to wrong source. When the user asks about anything they captured or seem to expect from saved notes (video summaries, topics, 'is this in my brain'), query gbrain FIRST with `gbrain search "<term>"` (binary at /root/.bun/bin/gbrain, not on PATH by default — export PATH="$HOME/.bun/bin:$PATH" and cd /root/gbrain -- note /root/gbrain has AGENTS.md that gets injected). Retrieval from `gbrain search` works headless; `gbrain think` stays silent without synthesis unless ANTHROPIC_API_KEY is set. To add: `gbrain capture --stdin` or `gbrain import <dir>` then it's searchable the same shell. Hermes now uses gbrain as its memory provider: custom plugin at /root/.hermes/plugins/gbrain/ (MemoryProvider ABC, shells to gbrain CLI: query=hybrid, search=FTS, salience=activity, capture JSON has slug), memory.provider=gbrain, MEMORY.md limit 800 (kept as tiny fallback; memory tool writes mirror into gbrain as [hermes:memory] captures). gbrain query/search text output parses as '[score] slug -- title' lines; 0.44.0.0 upgrade pending (don't auto-run — may change CLI output).
§
Latitude (latitude.so): project slug 'capital-empire-s-project'; LATITUDE_API_KEY in /root/gbrain/.env; CLI ~/.local/bin/latitude (run from /root/gbrain); gbrain instrumented via src/core/telemetry.ts (env-gated; GBRAIN_LATITUDE_DEBUG=1 logs).
§
User (Telegram) runs Hermes DESKTOP app on Windows (PowerShell, Windows username 'phemelo', folder C:\Users\phemelo\.ssh\) and connects to this VPS over SSH ('Connect via SSH' mode). This VPS: public IP 102.208.217.192, sshd socket-activated on :22, ufw was default-deny so port 22 had to be opened (now allowed); hermes binary at /usr/local/bin/hermes. User's SSH ed25519 keypair lives at C:\Users\phemelo\.ssh\id_ed25519\id_ed25519.pub. Screenshot-based OCR of base64 SSH keys is unreliable — always have the user paste key text directly (clip) instead.
§
test_quote_pool.py validates quote pool (100 picks, scratch state, no repeats).
§
User runs a YouTube-Shorts autoclipper pipeline at /root/autoclipping (Node orchestrator main.js + uv-run Python: scripts/extract.js yt-dlp cut, scripts/face_reframe.py MediaPipe 9:16 face-track, scripts/subtitles_oneline.py ASS burn; clips in data/clips.json, outputs in Outputs/NN_slug.mp4). Clips are user-reviewed via vision-model frame checks; when he reports a defect, he expects the fix in the pipeline code itself (idempotent, no double burns) rather than a one-off output patch.
§
/tmp ephemeral: files vanish between calls. Use project dir or /root for artifacts.
§
video-use skill: /root/video-use → ~/.hermes/skills/video-use; timeline_view.py EOF-seek fix — re-apply after git pull.
§
AgentMail inbox: phemeloagent-001@agentmail.to. Full API key in ~/.agentmail/credentials.json. Check inbox: curl GET /v0/inboxes/phemeloagent-001%40agentmail.to/messages with Bearer auth.
§
Hermes profile backup: git repo /root/hermes-profile-backup → private GitHub Fxzenith/hermes-profile-backup; daily 20:00 cron (backup_profile.sh, silent-on-success, Telegram alert on fail); monthly full zip → gh release. Restore runbook in repo README: clone + rsync to ~/.hermes.
§
Standing user rule (updated 2026-08-11): NO blanket kanban mirroring. Track tasks on the hermes kanban board ONLY when the /plan (default slash) skill was invoked that session; otherwise in-session tracking only. Caveat: sessions with HERMES_DELEGATED_CHILD_CONTEXT=1 are hard-blocked from the kanban CLI entirely (even kanban list) — that's a safety guard, not a broken board; do not bypass. Orphan card t_1f2f04e3 (hackernews-count-arg:1) was created but never completed due to that block — complete/archive it from a normal session.