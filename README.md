# Hermes Profile Backup

Daily auto-snapshot of `~/.hermes` (private repo, auto-pushed). Survives a full VPS reset.

- **Source:** `/root/.hermes`
- **Script:** `~/.hermes/scripts/backup_profile.sh` (sqlite-safe `state.db` snapshot + rsync mirror, excludes caches/lsp/bin/logs)
- **Cron:** daily 20:00 — silent on success, Telegram alert on failure
- **Repo:** https://github.com/Fxzenith/hermes-profile-backup (private)

## Restore after a full VPS reset

1. Reinstall Hermes: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
2. Clone: `git clone https://github.com/Fxzenith/hermes-profile-backup.git ~/hermes-profile-backup`
3. Stop the gateway if running: `hermes gateway stop`
4. Restore: `rsync -a ~/hermes-profile-backup/ ~/.hermes/` — first remove repo-only files:
   ```bash
   rm -f ~/hermes-profile-backup/.gitignore ~/hermes-profile-backup/README.md ~/hermes-profile-backup/MANIFEST.md
   rsync -a ~/hermes-profile-backup/ ~/.hermes/
   ```
5. Verify: `hermes chat -q "list my cron jobs and memories"`
6. Reinstall external tooling per `MANIFEST.md` (gbrain, autoclipping, REELS pipeline, venvs, AgentMail).

## Manual backup / test

```bash
~/.hermes/scripts/backup_profile.sh              # snapshot + commit + push
tail -f ~/.hermes/logs/backup_profile.log        # run history
```

## Layout

- `MANIFEST.md` — inventory of external assets NOT in this repo
- `state.db` — consistent SQLite snapshot of sessions/memory/cron state
- `config.yaml`, `.env`, `auth.json` — config + credentials (repo is PRIVATE — keep it that way)
- `skills/`, `memories/`, `cron/`, `sessions/`, `scripts/`, `plans/`, `checkpoints/` — the actual profile
