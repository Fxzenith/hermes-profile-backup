---
name: kanban-task-tracking
description: "Use when tracking tasks: update the hermes kanban board."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kanban, task-tracking, todo, planning, workflow]
---

# Kanban Task Tracking

Standing user rule (updated 2026-08-11): **mirror tasks to the Kanban board ONLY when the `/plan` skill (the default slash skill) was invoked in that session.** For ordinary tasks and todo lists, do NOT create kanban cards — keep tracking in-session only. The board is the durable record of planned work; the in-session todo list is the working view. Both the agent and the user (via `/kanban` in chat or the dashboard) see the same SQLite board at `~/.hermes/kanban.db`.

## Facts (verified on this box, 2026-08)

- Board: built-in `hermes kanban`, board slug `default`, DB `~/.hermes/kanban.db`.
- Drive it via terminal: `hermes kanban <verb>` — normal sessions have no `kanban_*` toolset (it appears only for dispatcher-spawned workers).
- Statuses: `triage | todo | ready | running | blocked | review | done | archived`. `create` defaults to **ready** (`--triage` → triage, `--initial-status {blocked,running}` → other). List glyphs: `▶` open, `⊘` blocked, `✓` done.
- `create` auto-attaches a worktree/scratch workspace (uses the board's default workdir / cwd project). Harmless for tracking; cards only get a real workspace when dispatched.
- One profile on this box: `default` (valid `--assignee`).

## Verified command shapes (exact, copy-paste)

```bash
# New tracked task → new card (default status: ready)
hermes kanban create "<JOB>:<n>: <title>" --idempotency-key <job>:<n>

# Blocked / waiting on user — REASON POSITIONAL FIRST, then --kind (argparse quirk)
hermes kanban block <id> "<reason>" --kind needs_input
# kinds: capability | dependency | needs_input | transient

# Progress note (the "in progress" signal for human-agent flows)
hermes kanban comment <id> "<note>"

# Task finished
hermes kanban complete <id> --summary "<short result>"

# Unblock / cancel
hermes kanban unblock <id>
hermes kanban archive <id>

# Read the board
hermes kanban list
hermes kanban show <id>
```

## The rule (mechanical, not judgment-based)

1. Every task in a plan written during a `/plan` session → `hermes kanban create` with a traceable title prefix (`<plan-slug>:<n>: <title>`). Ordinary (non-/plan) sessions: no cards.
2. Task blocked or waiting on the user → `hermes kanban block <id> "<why>" --kind needs_input`.
3. Meaningful progress / ready for review → `hermes kanban comment <id> "<note>"`.
4. Task finished → `hermes kanban complete <id> --summary "<result>"`.
5. Cancelled/obsolete → `hermes kanban archive <id>`.
6. Batch/retried runs → reuse the same `--idempotency-key`; a repeat create returns the SAME task id (verified: no duplicates).

## Pitfalls (learned the hard way)

- `block` argument order: `block <id> "<reason>" --kind <kind>` works; `block <id> --kind <kind> "<reason>"` FAILS with "unrecognized arguments".
- `--priority` takes an **int**, not strings like `high`.
- `block` without a kind fails with "cannot block <id>" (kind is required).
- `complete` takes one or more task ids as positionals; `--result`/`--summary` are optional but useful for the audit trail.
- A task already blocked can't be blocked again — unblock first.
- `hermes kanban boards switch <slug>` changes the default target; multi-board work should pass `--board <slug>` explicitly.
- Sessions with `HERMES_DELEGATED_CHILD_CONTEXT=1` in the env are hard-blocked from the kanban CLI entirely — even `list` fails with "delegate_task child contexts cannot mutate Kanban tasks or boards". It's a safety guard, not a broken board; don't try to bypass it. Just note the block and finish the work; sync the board from a normal session later if needed.
- Idempotency keys are per-create; use a stable scheme like `plan:<slug>:<n>`.

## Verification

After any tracking session: `hermes kanban list` should mirror the todo list 1:1 (same tasks, matching statuses). The user can cross-check with `/kanban list` in the chat.
