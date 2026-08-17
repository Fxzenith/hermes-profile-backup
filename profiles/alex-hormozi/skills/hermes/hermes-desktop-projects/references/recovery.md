# Restoring a wiped Hermes desktop Project

Verified 2026-08-07. Scenario: `project_create("New Project", path)` was run; a desktop/agent
reconcile then dropped an already-existing project record from `~/.hermes/projects.db` within
~60s, so it disappeared from the sidebar. DB integrity stayed `ok`. Recovery is a direct
`INSERT OR REPLACE` that restores the ORIGINAL identity (same `id`, `slug`, `name`) so the
sidebar shows the expected name and the earlier session/user handles still line up.

## 1. Confirm what's actually in the store

```bash
cd ~/.hermes
sqlite3 -header -column projects.db \
  "SELECT id,slug,name,archived,primary_path FROM projects;"
sqlite3 -header -column projects.db \
  "SELECT project_id,path,is_primary FROM project_folders;"
sqlite3 projects.db "PRAGMA integrity_check;"
```

A vanished record: row absent from `projects` (it may still appear in `strings -a projects.db`
on a freelist page — ignore that; trust the live read). `project_list` also drops it.

## 2. Restore the project record + its primary folder mapping

Use `INSERT OR REPLACE` so re-runs are idempotent. Preserve the original row's `id` and `slug`
(you can recover them from the earlier `project_list` output or from `strings -a projects.db`).

```bash
sqlite3 ~/.hermes/projects.db <<'SQL'
-- restore the project row (adjust id/slug/name/path/created_at to the original)
INSERT OR REPLACE INTO projects
  (id, slug, name, description, icon, color, board_slug, primary_path, created_at, archived)
VALUES
  ('p_cf60b51f', 'yt-clipper', 'Content pipeline', NULL,
   'folder-library', 'hsl(60 68% 58%)', NULL, '/root/autoclipping', 1785396446000, 0);

-- re-canonicalize the primary folder mapping (label = display name, is_primary = 1)
REPLACE INTO project_folders (project_id, path, label, is_primary, added_at)
VALUES ('p_cf60b51f', '/root/autoclipping', 'Content pipeline', 1, 1785396446000);
SQL
```

`created_at` is epoch ms. If unknown, any valid ms timestamp is fine.

## 3. Sweep orphan `project_folders` rows

Rows whose `project_id` no longer exists in `projects` reference deleted projects. They are
common after a repo relocation from a nested path (`a/b`) to a root path (`/b`). Sweep them
(guarded so it never touches real projects):

```bash
sqlite3 ~/.hermes/projects.db \
 "DELETE FROM project_folders WHERE project_id NOT IN (SELECT id FROM projects);"
```

## 4. Verify it sticks (the sync can re-wipe it)

```bash
sleep 6
sqlite3 -header -column ~/.hermes/projects.db \
  "SELECT id,name,archived,primary_path FROM projects;"
```

Then call the `project_list` tool and confirm both/all projects appear. If the record survives
the beat, the fix is durable. If it is re-wiped, the desktop-side project sync is actively
overwriting the store and the durable fix is to recreate the project from the **desktop UI's**
project button rather than the agent tool.

## Key diagnostics used to find this

- `stat -c '%y' ~/.hermes/projects.db` → DB last-touched time. Compare against `~/.hermes/logs/agent.log`
  timestamps around when you ran `project_create`/`project_list` to pin exactly when a record vanished
  (here: existed at 14:22:25, gone by 14:23 — a write ~60s after create, not the create itself).
- `grep -i project agent.log` → confirms what the agent actually ran and when.
- `strings -a projects.db | grep -i <slug>` → recover the original row's exact `id`/`slug`/
  `name`/`color`/`icon` you need to restore faithfully.