# Hermes Profile Backup Repo — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Create a private, versioned git repo that snapshots the entire Hermes profile (`~/.hermes`), auto-pushed daily, so that if this VPS is wiped/reset we can clone it back, restore, and continue exactly where we left off — memory, skills, cron jobs, sessions, config, and credentials intact.

**Architecture:** A git repo at `~/hermes-profile-backup` mirrors the live profile via an rsync-based backup script (with a SQLite-consistent `state.db` snapshot via `sqlite3 .backup`), excluding regenerable caches. A daily cron job commits and pushes silently on success and alerts on failure. Restore = clone + rsync back into `~/.hermes` + `hermes` reinstall (one command). Validation uses `HERMES_HOME` staging so the live profile is never touched during tests.

**Tech Stack:** bash + rsync + sqlite3 (backup), git 2.43 + GitHub CLI `gh` (repo hosting, authed as `Fxzenith`), Hermes built-in `cronjob` tool (scheduling), Hermes `hermes backup` / `hermes profile export` (secondary artifacts, optional).

---

## Context & findings (verified this session)

**"Premium backup" search result:** The web search for "how to create premium backup" returns only commercial backup products — Seagate Memeo Premium, SiteGround Premium Backup service, UpdraftPlus Premium, "Backup Premium" shareware. None of these apply to Hermes; there is no Hermes feature called "premium backup." What Hermes actually ships for this job is `hermes backup` (full/quick zip), `hermes profile export|import|install` (profile archives, git-installable distributions), and checkpoints. **Decision:** the raw-content git repo below is the primary mechanism because it is versioned, diffable, and restores byte-for-byte; `hermes backup` zip is offered as an optional monthly artifact (Task 8).

**Verified on this box (Aug 11 2026):**
- `hermes backup [-o OUT] [-q] [-l LABEL]` and `hermes profile {export,import,install,update}` exist in the local CLI (docs pages were unreachable via web_extract — auth failure — but local `--help` output is authoritative).
- `gh` CLI is logged in as **github.com/Fxzenith** with full scopes (`repo`, `workflow`, `delete_repo`, …) → can create and push to a private repo.
- `git 2.43.0` present, but **no global `user.name`/`user.email` set** → Task 1 must set identity or commits fail.
- `sqlite3` (for consistent DB snapshot), `rsync`, `tar` all present.
- Disk: 16G free on `/` — plenty for a ~150M repo.
- Default profile lives at `~/.hermes/` root (no `~/.hermes/profiles/<name>` dir); `~/.hermes/profile.yaml` confirms it.

**~/.hermes size breakdown (320M total):**

| Path | Size | Include in repo? |
|---|---|---|
| `lsp/` | 88M | ❌ regenerable |
| `bin/` | 76M | ❌ launcher binaries, reinstalled by installer |
| `skills/` | 51M | ✅ core (incl. video-use, all custom skills) |
| `checkpoints/` | 43M | ✅ file-versioning history, small enough |
| `state.db` | 41M | ✅ via `sqlite3 .backup` (consistent copy) |
| `logs/` | 8.2M | ❌ |
| `sessions/` | 5.2M | ✅ transcripts + routing index |
| `models_dev_cache.json` + other caches | ~4M | ❌ |
| `cron/`, `memories/`, `config.yaml`, `.env`, `auth.json`, `SOUL.md`, `scripts/`, `plans/`, `kanban.db`, `projects.db`, `gateway_state.json`, `desktop-ssh/`, `platforms/`, `pairing/`, `pets/`, `desktop-plugins/`, `tui-widgets/` | ~15M | ✅ |
| `state.db-wal/-shm`, `cache/`, `image_cache/`, `audio_cache/`, `runtime/`, `sandboxes/`, `desktop/`, `*.lock`, `*.pid`, `.update_check` | — | ❌ |

**Estimated repo size after excludes: ~150–170 MB** — well under GitHub's 100 MB/file and repo limits; `state.db` (41M) is the largest single file. Growth risk is flagged in Risks.

## Assumptions

1. The backup repo is **private** (it contains `.env` API keys and `auth.json` OAuth tokens). Public exposure = credential leak.
2. "Everything resets" means the VPS is re-provisioned (filesystem wiped). Restore target is a fresh Linux box with `gh`/git access restored, or credentials pasted manually.
3. The gateway may be running during backup — the script must be safe against live writes (hence `sqlite3 .backup`, which is an online-safe snapshot API; rsync of other files is atomic-enough for this purpose).
4. Secret-encryption (age/gpg) is **not** in scope initially; private-repo access control is the trust boundary. Flagged as an open question.
5. External project dirs (`/root/gbrain`, `/root/autoclipping`, REELS pipeline, `~/.venvs`, `~/.agentmail`) are **out of scope** for this repo unless the user opts in (open question) — they're captured in a manifest file (Task 4) so nothing is forgotten.

## Proposed repo layout

```
~/hermes-profile-backup/
├── README.md                 # restore runbook (Task 7)
├── MANIFEST.md               # external dirs + credentials inventory (Task 4)
├── .gitignore
├── config.yaml  profile.yaml  .env  auth.json  SOUL.md  ...
├── skills/  memories/  cron/  sessions/  scripts/  plans/  checkpoints/
├── state.db                  # clean snapshot from sqlite3 .backup
└── kanban.db  projects.db  verification_evidence.db  gateway_state.json ...
```

## Tasks

### Task 1: Set git identity + create private GitHub repo

**Objective:** Make git commits possible and create the remote home for the backup.

**Step 1: Set global git identity**

```bash
gh api user --jq '"\(.login) <\(.id)+\(.login)@users.noreply.github.com>"'   # → Fxzenith <ID+Fxzenith@users.noreply.github.com>
git config --global user.name "Fxzenith"
git config --global user.email "<the noreply address from the command above>"
```

Expected: both `git config --global user.name` and `user.email` print values (currently empty).

**Step 2: Create private repo**

```bash
gh repo create hermes-profile-backup --private --description "Hermes agent profile backup (auto-pushed daily)" --confirm
```

Expected: `https://github.com/Fxzenith/hermes-profile-backup` created.

**Step 3: Commit**

```bash
cd ~/hermes-profile-backup && git init -b main && git commit --allow-empty -m "chore: init backup repo"
```

Expected: empty initial commit exists. (`gh repo create` may already init+push; adapt if so.)

---

### Task 2: Write the backup script

**Objective:** One idempotent script that snapshots `~/.hermes` into the repo, commits, and pushes — safe to run while the gateway is live.

**Files:**
- Create: `~/.hermes/scripts/backup_profile.sh`

```bash
#!/usr/bin/env bash
# Hermes profile backup: snapshot -> commit -> push. Silent on success (logs to file).
set -euo pipefail
SRC="$HOME/.hermes"
DST="${BACKUP_DEST:-$HOME/hermes-profile-backup}"
LOG="${BACKUP_LOG:-$HOME/.hermes/logs/backup_profile.log}"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

# 1. Consistent snapshot of the live SQLite session store (WAL-safe, online backup API)
sqlite3 "$SRC/state.db" ".backup '$DST/state.db'"

# 2. Mirror everything else, excluding regenerable data
rsync -a --delete \
  --exclude='cache/' --exclude='logs/' --exclude='lsp/' --exclude='bin/' \
  --exclude='image_cache/' --exclude='audio_cache/' --exclude='runtime/' \
  --exclude='sandboxes/' --exclude='desktop/' \
  --exclude='state.db*' --exclude='*.lock' --exclude='*.pid' \
  --exclude='models_dev_cache.json' --exclude='ollama_cloud_models_cache.json' \
  --exclude='provider_models_cache.json' --exclude='.update_check' \
  --exclude='.mcp-discovery.lock' --exclude='processes.json' \
  "$SRC/" "$DST/"

# 3. Commit + push only when something changed
cd "$DST"
git add -A
if git diff --cached --quiet; then
  log "no changes, skipping"
  exit 0                                    # empty stdout = cron stays silent
fi
git commit -q -m "backup: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push -q origin HEAD
log "committed and pushed"
```

**Step 2: Make executable + syntax check**

```bash
chmod +x ~/.hermes/scripts/backup_profile.sh && bash -n ~/.hermes/scripts/backup_profile.sh
```

Expected: no output, exit 0.

---

### Task 3: Populate the repo + .gitignore

**Objective:** First real snapshot lands in the repo.

**Step 1: Create `.gitignore`** at `~/hermes-profile-backup/.gitignore` (belt-and-suspenders on top of rsync excludes):

```gitignore
cache/
logs/
lsp/
bin/
image_cache/
audio_cache/
runtime/
sandboxes/
desktop/
state.db-wal
state.db-shm
*.lock
*.pid
models_dev_cache.json
ollama_cloud_models_cache.json
provider_models_cache.json
.update_check
```

**Step 2: First snapshot**

Run: `BACKUP_DEST="$HOME/hermes-profile-backup" ~/.hermes/scripts/backup_profile.sh`
Expected: exit 0; `~/hermes-profile-backup/` now contains config.yaml, .env, auth.json, SOUL.md, skills/, memories/, cron/, sessions/, scripts/, plans/, checkpoints/, state.db, kanban.db, etc.; `git status` shows them staged.

**Step 3: Sanity-check the staged tree**

```bash
cd ~/hermes-profile-backup && git status --short | head -30 && git status --short | wc -l
du -sh ~/hermes-profile-backup
```

Expected: plausible file count (hundreds, mostly under `sessions/` and `skills/`), repo size ≈150–170M, **no** `lsp/`/`bin/`/`logs/`/cache dirs present.

---

### Task 4: Initial commit, push, and write MANIFEST.md

**Objective:** Backup is off-box for the first time; external deps are inventoried so nothing is forgotten in a reset.

**Step 1: Write `MANIFEST.md`** in the repo listing what lives **outside** `~/.hermes` that a full restore also needs:

```markdown
# External assets (not in this repo)
- /root/gbrain         — second brain (PGLite DB ~/.gbrain/brain.pglite, bun CLI, NVIDIA embeddings)
- /root/autoclipping   — YouTube Shorts autoclipper pipeline
- REELS pipeline       — cron 7a4c465fbd09: scripts/reel_post.py, music/ (11 tracks), .env with PIXABAY_API_KEY
- ~/.venvs/*           — Python venvs (PEP 668)
- ~/.agentmail/        — AgentMail credentials
- /root/.bun, /root/.local/bin/latitude  — CLI tools (reinstallable)
```

**Step 2: Commit + push**

```bash
cd ~/hermes-profile-backup
git add -A && git commit -m "backup: initial profile snapshot $(date -u +%Y-%m-%d)"
git push -u origin main
```

**Step 3: Verify remote**

```bash
git ls-remote origin | head -3
```

Expected: `refs/heads/main` listed. Repo now at `https://github.com/Fxzenith/hermes-profile-backup` (private).

---

### Task 5: Staged restore test (never touches the live profile)

**Objective:** Prove the "everything resets" recovery path actually works, using `HERMES_HOME` staging.

**Step 1: Simulate a fresh install**

```bash
git clone https://github.com/Fxzenith/hermes-profile-backup.git /tmp/restore-test
mkdir -p /tmp/test-home
rsync -a /tmp/restore-test/ /tmp/test-home/
rm -f /tmp/test-home/.gitignore /tmp/test-home/README.md /tmp/test-home/MANIFEST.md
```

**Step 2: Boot Hermes against the restored profile**

```bash
HERMES_HOME=/tmp/test-home hermes chat -q "Report which profile you're running, then list your memory entries and your cron jobs." 
```

Expected: output shows restored config (provider, model), restored memories (gbrain, REELS, VPS details), and cron jobs (7a4c465fbd09 REELS 18:00 + 11:00 image post). If boot fails, fix restore path (usually a missing dir like `memories/` or `cron/` that rsync didn't carry — adjust script).

**Step 3: Clean up staging**

```bash
rm -rf /tmp/restore-test /tmp/test-home
```

Expected: gone; live `~/.hermes` untouched (verify: `hermes chat -q "still running from default profile"` still works).

---

### Task 6: Daily auto-backup cron

**Objective:** The repo stays fresh with zero manual steps; failures alert loudly.

**Step 1: Create the cron job** (Hermes cronjob tool)

- schedule: `0 3 * * *` (daily 03:00)
- `no_agent: true` — script IS the job
- `script: ~/.hermes/scripts/backup_profile.sh`
- deliver: origin (default)

Expected: `cronjob list` shows the job. Semantics: empty stdout on success = silent; non-zero exit = Hermes sends an error alert (broken backup can't fail silently). The script already logs every run to `~/.hermes/logs/backup_profile.log`.

**Step 2: Test-fire it**

Run the job once via `cronjob action='run'`. Expected: completes with no delivery; `tail ~/.hermes/logs/backup_profile.log` shows either "no changes" or "committed and pushed"; `git -C ~/hermes-profile-backup log --oneline -3` shows today's commit if anything changed.

---

### Task 7: Write the restore runbook (README.md)

**Objective:** A stranger (or future-you) can rebuild this box in under 10 minutes.

**Files:**
- Create: `~/hermes-profile-backup/README.md`

```markdown
# Hermes Profile Backup
Daily auto-snapshot of ~/.hermes (private). Restore after a full VPS reset:

1. Reinstall Hermes:  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
2. Clone:            git clone https://github.com/Fxzenith/hermes-profile-backup.git ~/hermes-profile-backup
3. Stop gateway if running: hermes gateway stop
4. Restore:          rsync -a ~/hermes-profile-backup/ ~/.hermes/   (rm .gitignore README.md MANIFEST.md first)
5. Verify:           hermes chat -q "list my cron jobs and memories"
6. Re-point cron if needed; reinstall external tooling per MANIFEST.md
```

**Step 2: Commit + push** (same pattern as Task 4 Step 2). Expected: README visible on GitHub.

---

### Task 8 (optional): Monthly full `hermes backup` zip → GitHub Release

**Objective:** A single-file, point-in-time archive as belt-and-suspenders (git history stays lean; zip captures even excluded dirs).

```bash
hermes backup -o /tmp/hermes-full-$(date +%Y%m%d).zip
gh release create "full-$(date +%Y%m%d)" /tmp/hermes-full-$(date +%Y%m%d).zip --repo Fxzenith/hermes-profile-backup --title "Full backup $(date +%Y-%m-%d)"
```

Note: `hermes backup` full zip is ~300M+ (includes lsp/bin/logs). Keep only the 2 most recent releases. **Skip unless user wants this** — the git repo already covers everything needed to continue.

---

## Validation summary

| Check | Command | Pass condition |
|---|---|---|
| Repo exists & private | `gh repo view Fxzenith/hermes-profile-backup` | private repo listed |
| Snapshot complete | `ls ~/hermes-profile-backup/{config.yaml,.env,skills,memories,cron}` | all present |
| No junk in repo | `du -sh ~/hermes-profile-backup` + spot-check | ≈150–170M, no lsp/bin/logs/cache |
| Push works | `git ls-remote origin` | main branch visible |
| Restore works | Task 5 staged test | Hermes boots from `/tmp/test-home` with memories + cron intact |
| Cron fires | Task 6 Step 2 | log line + commit appears |
| Live profile untouched | post-test `hermes chat -q` | normal reply |

## Risks, tradeoffs, open questions

- **Secrets in a git remote:** `.env` and `auth.json` are in the repo. Mitigation: repo is **private**; GitHub token already has repo scope. Hardening option: encrypt `.env`/`auth.json` with `age` before commit and decrypt in the backup script — ask user if they want this (adds key-management complexity).
- **`state.db` growth:** 41M now; git history grows with every commit that touches it. Fine for ~1–2 years of daily commits, then consider `git lfs` or switching `state.db` to a weekly snapshot. Checkpoint: GitHub warns >100 MB per file; `state.db` has headroom.
- **`checkpoints/` (43M) included:** grows with file-versioning activity. If it balloons, move to the monthly zip only.
- **Live-write races:** `sqlite3 .backup` is online-safe; individual files under `sessions/` could be mid-write during rsync — worst case a torn transcript in one commit, self-heals next run. Accepted.
- **`sessions/` contains 26 request dumps (private transcripts):** reinforces the private-repo requirement.
- **Open question:** should `/root` project dirs (gbrain, autoclipping, REELS pipeline + music/, agentmail creds) be added to this repo (as a `projects/` tree) or backed up separately? They're the difference between "Hermes restored" and "everything restored."
- **Open question:** repo name — `hermes-profile-backup` used throughout; rename freely.
- **Open question:** git identity email — plan uses GitHub noreply (`ID+Fxzenith@users.noreply.github.com`) to avoid exposing a personal email; swap for the account's real email if preferred.
