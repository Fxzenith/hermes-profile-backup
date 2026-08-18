# Keeping local patches alive on a symlinked skill-first repo

When you `git clone` a skill-first repo (it ships its own `SKILL.md` + helpers) and `ln -sfn` it into `/root/.hermes/skills/<name>`, any local edit to that `SKILL.md` is **reverted on the next `git pull`**. Two cases need durability:

## Case A — you renamed the skill
User wants a short skill name (e.g. `diagram-design` → `diagram`). You patched the `name:` in frontmatter. Protect it:

```bash
cd /root/<repo>
git update-index --skip-worktree skills/<subpath>/SKILL.md
```

`skip-worktree` tells git to ignore local changes to that one file, so `git pull` won't clobber your rename. Verify with `git ls-files -v | grep ^S`.

## Case B — you recorded the patch somewhere
Because the persistent memory backend can reject writes on a headless box, keep an on-disk ledger of local patches instead of relying on memory round-trips:

```markdown
# LOCAL_PATCHES.md (repo root)
- Renamed skill `diagram-design` -> `diagram` (SKILL.md frontmatter `name:`).
  Protected via `git update-index --skip-worktree skills/diagram-design/SKILL.md`.
  Re-apply after a hard `git checkout` / re-clone.
```

## Re-apply after a destructive reset
If the repo is re-cloned or `git checkout -- .` is run, skip-worktree is lost — redo the frontmatter edit + `skip-worktree`. The ledger is the single source of truth for what to re-apply.

## Do NOT
- Edit the upstream repo's content and expect it to survive a pull — only `skip-worktree`-marked files are protected, and only the one file.
- Treat a memory-store failure as "the patch is saved" — it isn't, until it's on disk (LOCAL_PATCHES.md) or in skip-worktree.
