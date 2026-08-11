---
name: hermes-desktop-projects
description: Repair a Hermes project missing from the desktop sidebar.
---

# Hermes Desktop Projects — data model & recovery

Hermes desktop shows a **PROJECTS sidebar** that groups sessions under project folders (e.g. `Home`, `gbrain`, `Content pipeline`). When a project "disappears" from that sidebar, the cause is almost always the project record dropping out of the persistent store on the agent side, not a UI glitch. This skill covers how projects are stored, how to verify what the store actually contains, and how to restore a vanished project.

## Where project state lives (server/agent side)

- **`~/.hermes/projects.db`** — the authoritative project store. Tables:
  - `projects` — `id` (PK), `slug` (UNIQUE), `name`, `description`, `icon`, `color`, `board_slug`, `primary_path`, `created_at`, `archived`.
  - `project_folders` — workspace folder mapping: `(project_id, path, label, is_primary, added_at)`, PK `(project_id, path)`. `is_primary=1` marks the anchor folder.
  - `project_meta` — key/value (e.g. `repo_discovery_policy`, `active_id` = the currently active project).
  - `discovered_repos` — auto-discovered git repos surfaced as candidate projects.
- **`~/.hermes/state.db`** — session store. Its `sessions` table has **NO project column**; it carries `cwd`, `git_repo_root`, etc. Do NOT expect to find project linkage here.

**Sidebar grouping rule:** the desktop sidebar renders project folders + their sessions from `projects.db` (project record + its `project_folders` primary path) matched against session workspaces. A project shows up only if its record exists in `projects.db`. Sessions whose workspace belongs to no project fall under `Home`.

> A `strings -a projects.db | grep ...` read may show rows for projects you don't see in a live `SELECT`. Those are leftovers on freelist/dead pages from earlier deletes — trust the live SQLite read, not `strings`.

## Standard commands

```bash
cd ~/.hermes
sqlite3 -header -column projects.db "SELECT id,slug,name,archived,primary_path FROM projects;"
sqlite3 -header -column projects.db "SELECT project_id,path,is_primary FROM project_folders;"
sqlite3 projects.db "PRAGMA integrity_check;"
# what last touched the store (hint at who dropped a record):
stat -c '%y' ~/.hermes/projects.db
```

Cross-check against the tool layer: `project_list` (returns `active_id` + all projects) — it reads the same store.

## Pitfalls (learned the hard way)

1. **Creating a new project can wipe an existing one.** `project_create(name, path)` records the new project and switches the chat into it; a follow-on desktop/agent reconcile then dropped the previously-existing project record within seconds (log: both existed at create time, one gone ~60s later). **After any `project_create`, re-run `project_list` AND re-query `projects.db` a few seconds later** before trusting the setup. If a sibling vanished, restore it (see `references/recovery.md`).
1a. **`project_create` does NOT create the anchor folder on disk.** It only writes the `projects` + `project_folders` rows and names `path` as `primary_path` — the directory itself is never `mkdir`'d. After calling it, `mkdir -p "<path>"` explicitly, then verify the folder exists before claiming the project is usable. Otherwise the project points at a nonexistent path (and a later `ls`/open fails). Full create-from-scratch sequence: `project_create(name=..., path="...")` → `mkdir -p "<path>"` → confirm with `ls`, `project_list` (record present) and a re-check a few seconds later (no sibling wiped).
2. **`project_create` has side effects** — it moves THIS chat into the new project. If you only want to add a project record and keep the current chat where it is, restore/mutate `projects.db` directly instead of calling `project_create`.
3. **Stale orphan folder rows** point at dead nested paths (e.g. `a-repo-a/b-repo-b` left over after a repo relocated to `/b-repo-b`). They orphan `project_folders` rows whose `project_id` no longer exists in `projects`. Sweep them when cleaning up.
4. **Don't panic-restart / don't "reinstall".** The record is recoverable via direct DB insert; no reboot or `hermes` reset needed.
5. `projects.db` is data, not config — direct sqlite edits are the intended low-level fix path. (Hand-editing `config.yaml` stays off-limits; that's a different rule.)

## Workflow: a project is missing from the sidebar

1. `project_list` → is the record gone from the agent side too, or only the UI?
2. `sqlite3 projects.db "SELECT ... FROM projects;"` → confirm whether the row exists.
3. If the row is gone, restore it (see `references/recovery.md`).
4. Verify `project_list` shows it, and re-check the DB after a short beat to confirm nothing re-wipes it.

## References
- `references/recovery.md` — exact SQL to restore a wiped project record + folder mapping and sweep orphans.