---
name: repo-as-skill
description: Use when adding a GitHub repo to this box as a skill.
---

# Adding a GitHub Repo as a Hermes Skill

The user's recurring request: "add this repo then create a skill of it" (often with a screenshot of the repo page). Deliverable: the repo cloned somewhere stable, its capability usable (installed + verified), and a discoverable skill. The user expects a *working artifact backed by real runs*, not an install description.

## When to Use

- User points at a GitHub repo and asks to "add" it / "make a skill of it"
- A repo screenshot is pasted — if you can't read the full path, resolve the repo via GitHub API first (below) instead of guessing from OCR
- Don't use for: repos that are just npm/pip libraries with no agent-facing workflow — plain installs, no skill

## Workflow

1. **Identify.** Screenshot with readable text → search GitHub: `curl -s "https://api.github.com/search/repositories?q=<name>&sort=stars&per_page=5"` and pick the row whose description matches the screenshot's one-liner. Never clone a guessed path.
2. **Clone** to `/root/<name>` (shallow: `git clone --depth 1`). `/tmp` is ephemeral on this box — repos live under /root.
3. **Read the shape** before deciding install path:
   - `README.md` → what it does + its own "setup prompt" (a repo that says "paste this into your agent… register the skill" is skill-first)
   - `pyproject.toml` → `[project.optional-dependencies]` extras (markitdown: `[all]`; bare install = no converters)
   - Does it ship its own `SKILL.md` + `helpers/`? Then it IS a skill repo.
4. **Path A — repo ships SKILL.md (skill-first).** Symlink, don't copy: `ln -sfn /root/<name> /root/.hermes/skills/<name>`. The repo's `SKILL.md` references helpers by bare name (`render.py`) — they stay discoverable as long as SKILL.md and helpers remain siblings, which the symlink preserves. Install deps (repo-local `.venv` via `uv sync` or `python3 -m venv .venv && .venv/bin/pip install -e .`), stage `.env` from `.env.example` with placeholder secrets — tell the user which key to paste, never invent one.
5. **Path B — plain tool repo.** Install into a dedicated venv (`/root/.venvs/<name>`, PEP 668 box — never system pip), with the full extras (`'markitdown[all]'`), then `skill_manage(action='create')` with a ≤60-char description.
6. **Verify per install.md's own contract:** "run one real command against one real file." Generate a fixture (ffmpeg `testsrc`/`sine`, openpyxl xlsx, python-pptx), run the CLI/helper end-to-end, and confirm rc==0 + sensible output. A version banner alone is not verification.
7. **Memory.** Compact entry: path, symlink/venv location, `.env` requirements (see worked examples below).

## SKILL.md description budget (create-time hard limit)

`skill_manage(action='create')` **rejects** a description over **60 chars** (validation error naming the char count) — this is stricter than the 1024-char validator limit the in-repo authoring docs mention, and the index only displays ~57 chars of it anyway.

- Format: one sentence, trigger first, ends with a period, all within 60 chars.
  - `Use when adding a GitHub repo to this box as a skill.` (53 ✓)
- **Do not retry a too-long description with cosmetic tweaks.** Three failed `skill_manage` calls in a row trip the `same_tool_failure_halt` guard and hard-stop the tool for the rest of the turn. Fix the description first (drop words until it fits), then retry once.

## Pitfalls

- **Same-tool failure guard:** after two failures of the same tool call, stop and diagnose (read the error, fix the arg) rather than shaving a word and resubmitting.
- **Repo-local patches vs upstream pulls.** If you fix an upstream bug locally (e.g. an EOF-seek clamp in a helper), the fix is lost on the next `git pull`.  Save "re-apply after git pull" in memory.
- **Disk pressure:** this box runs at ~90%+ full — use `--no-cache-dir` on pip/uv installs, `df -h` first, keep fixtures small.
- **venv Python vs script shebangs:** helpers may import heavy, deps. Run them with the venv's python (`/root/.venvs/<name>/bin/python` or `<repo>/.venv/bin/python`), not bare `python3` from system PATH.
- **`git pull` on the live clone** if behavior looks stale before recommending commands.
- **Local skill rename lost on pull.** If you patched a skill name (e.g. `diagram-design`→`diagram`) on a symlinked skill-first repo, protect it with `git update-index --skip-worktree <path>/SKILL.md` and keep an on-disk `LOCAL_PATCHES.md` ledger — see `references/local-patch-durability.md`. Don't rely on the memory backend for durability on a headless box; it can reject writes.

## Worked examples

`references/worked-examples.md` — the two real installs: markitdown (tool repo → venv → skill_manage) and browser-use video-use (skill repo → symlink), with exact commands, quirks, and verification steps.