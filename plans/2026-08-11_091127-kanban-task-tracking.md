# Kanban Task-Tracking Board — Implementation Plan (Built-in `hermes kanban`)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Use Hermes's built-in Kanban board (`hermes kanban`, SQLite-backed at `~/.hermes/kanban.db`) as the shared task tracker, and make "update the board whenever tracking tasks" a permanent part of the agent's workflow.

**Architecture:** No external services, no custom code. The board already exists (default board, empty, on this VPS). The agent updates it via `hermes kanban` CLI verbs over the terminal; the user views it via the `/kanban` slash command in the desktop chat and optionally the dashboard's Kanban tab. The convention ("every tracked task = one board card, kept current as it moves through its lifecycle") is encoded in a skill so every future session follows it automatically.

**Tech Stack:** Hermes built-in kanban (`hermes kanban` CLI, `/kanban` slash command, `kanban_*` toolset, dashboard Kanban tab), git repo optional (no code to write), skills system for the standing rule.

---

## 1. Why the built-in kanban (supersedes the GitHub Projects plan)

The earlier plan (`2026-08-11_091127-kanban-task-tracking.md` draft) proposed GitHub Projects v2 + a custom `kanban` CLI wrapper. That was written before verifying what Hermes ships. The built-in board wins on every axis:

| | GitHub Projects v2 (old plan) | Built-in `hermes kanban` (this plan) |
|---|---|---|
| Infrastructure | external service, token scopes | SQLite on the VPS, already initialized |
| Agent side | custom wrapper CLI + tests | native `hermes kanban` CLI + `kanban_*` tools |
| User side | browser on github.com | `/kanban` slash command in the desktop chat; dashboard Kanban tab |
| Columns | 4 (custom) | 8 native: `triage · todo · ready · running · blocked · review · done · archived` |
| Human-in-the-loop | none | comments, `block`/`unblock` at any point, review status |
| Durability | depends on GitHub | durable rows in SQLite, survives restarts |
| Cost | free | zero |

**Verified on this VPS:** `hermes kanban` CLI present with full verb set (`init, boards, create, list, show, assign, comment, complete, block, unblock, schedule, promote, archive, …`); `hermes kanban list` works; board `default` exists and is empty. Docs (features/kanban) confirm both surfaces route through the same `kanban.db` so agent and human never drift.

## 2. Assumptions

- Single workstream → stay on the **default** board (docs: "Single-project users stay on the default board and never see the word 'board'"). A named board is a one-command change later (`hermes kanban boards create ops --switch`).
- This session (and future normal sessions) has no `kanban_*` toolset enabled → the agent updates the board with `hermes kanban <verb>` via the terminal tool. Works identically in cron and one-shot sessions.
- Card titles carry a traceable prefix (e.g. `P12-T3: <title>`) so cards map 1:1 to plan tasks / todos.
- Statuses used day-to-day: `todo` (created/backlog), `running` (in progress), `blocked` (stuck), `review` (needs user check), `done` (completed). `triage`/`ready`/`archived` exist natively but are optional.
- The board is the durable record; the in-session todo list is the working view. No two-way mirror needed — same DB.

## 3. Files likely to change

- `~/.hermes/kanban.db` — the board itself (runtime data)
- `~/.hermes/kanban/` — workspaces/logs (runtime data)
- Skill: `kanban-task-tracking` (the standing rule, created via `skill_manage`)
- `.hermes/plans/` — future plans gain a "update kanban" step per task (dogfooded in this plan)

---

## 4. Tasks

### Task 1: Verify and configure the board

**Objective:** Confirm the board is live and pin its display identity.

**Step 1: Health check**

Run:
```bash
hermes kanban boards list
hermes kanban init          # idempotent; no-op if DB exists
hermes kanban list
```
Expected: `default` board present, init no-ops, `list` prints `(no matching tasks)`.

**Step 2: Rename display name (optional but nice)**

Run: `hermes kanban boards rename default "Ops"` (slug stays `default`; cosmetic only). If a rename is unwanted, skip — nothing depends on it.

**Step 3: Confirm status vocabulary**

Run: `hermes kanban create --help`
Expected: flags match the docs statuses (`--initial-status {blocked,running}`, `--priority`, `--idempotency-key`, …). Record the `--idempotency-key` flag — used for dedup in Task 3.

**Step 4: Commit**

No repo; this task is remote state. Record any decisions (board name) for the skill in Task 3.

---

### Task 2: Pin the workflow convention (the mapping table)

**Objective:** Define exactly how tracked tasks map to board operations, so the rule is mechanical, not judgment-based.

**Files:** none (documented in the skill in Task 3)

**Step 1: Define the lifecycle mapping**

| Tracked-task event (in-session) | Board operation |
|---|---|
| New task added to todo list / plan | `hermes kanban create "<PREFIX: title>" --priority <p>` (status `todo`) |
| Work starts on the task | `hermes kanban create ... --initial-status running` (create-then-start) or re-create on claim; simplest: create with `todo`, then `hermes kanban` has no `start` verb → set `running` via the dispatcher/claim. **Fallback convention:** leave status `todo` until completion; use comments for progress notes; `running` is set automatically when a dispatcher claims the task. For the human-agent workflow the meaningful transitions are: `todo → blocked → review → done`. |
| Task blocked / waiting on user | `hermes kanban block <id> --reason "…"` |
| Task needs user validation | `hermes kanban comment <id> "ready for review"` (status stays; `review` is set by `--initial-status`/promote if used) |
| Task completed | `hermes kanban complete <id>` |
| Task cancelled / obsolete | `hermes kanban archive <id>` |
| Progress note mid-task | `hermes kanban comment <id> "<note>"` |

**Step 2: Define dedup (idempotency)**

- Preferred: `--idempotency-key <stable-key>` at create time (e.g. `plan:<plan-slug>:task:<n>`). Re-running the same create is a no-op — safe for cron/retry.
- Fallback (no key support in the verb used): before creating, run `hermes kanban list --format json` (verify the flag; else plain `list`) and skip if a card with the same title prefix exists.

**Step 3: Verify a full lifecycle live**

Run:
```bash
hermes kanban create "T-0: smoke test card"
hermes kanban list
hermes kanban block T-0 "waiting on user"
hermes kanban comment T-0 "ready for review"
hermes kanban complete T-0
hermes kanban list
```
(Use the real task id from `create` output.) Expected: card appears in `todo`, then `blocked`, then `done`, with one comment — all visible in `list`/`show`.

---

### Task 3: Encode the standing rule as a skill

**Objective:** Make "always update the Kanban board when tracking tasks" automatic for every future session.

**Files:**
- Create: skill `kanban-task-tracking` via `skill_manage(action="create", name="kanban-task-tracking", category="hermes")`

**Step 1: Create the skill**

Content must include:
- **Trigger:** whenever tracking tasks (todo tool, plan execution, multi-step jobs) — standing user request.
- **Facts:** board = built-in `hermes kanban`, default board, DB `~/.hermes/kanban.db`; drive via terminal `hermes kanban <verb>` (no `kanban_*` tools in normal sessions); statuses `triage|todo|ready|running|blocked|review|done|archived`.
- **Commands:** the mapping table from Task 2 (create/block/comment/complete/archive) plus `list`, `show <id>`, `unblock <id>`.
- **Rule:** every tracked task gets a card at creation; every status change is mirrored with one command; card titles prefixed `<plan-or-job>:<n>: <title>`; dedup via `--idempotency-key` or title check.
- **Pitfalls:** the board has no `start` verb — `running` is dispatcher-set; use `todo` + comments for human-agent flow; `complete` needs the real task id (from `create` output or `list`); `--board <slug>` scopes multi-board setups; `hermes kanban boards switch <slug>` changes the default target.

**Step 2: Verify the skill loads**

Run: `skill_view(name="kanban-task-tracking")` — content renders, no `[SKILL_PRUNED]` markers.

**Step 3: Dogfood it**

Create one card exactly as the skill prescribes, complete it, archive the test card. Confirm `hermes kanban list` reflects it.

---

### Task 4: The user's viewing surfaces

**Objective:** Confirm the user can watch the board from his Windows machine, and set up the visual option.

**Step 1: Slash command (primary, zero setup)**

In the desktop chat, run: `/kanban list` (and `/kanban show <id>`).
Expected: the same board content the agent sees. This works over the existing SSH-mode gateway — no ports, no tokens. This is the day-to-day surface.

**Step 2: Dashboard Kanban tab (visual, optional)**

The docs describe `hermes dashboard` → Kanban tab (board switcher, New board modal, live board). Verify locally:
```bash
hermes dashboard   # or check `hermes dashboard --help` for host/port flags
```
Then decide access: the VPS firewall is locked (ufw default-deny). Do **not** open a public port. Use an SSH tunnel from the user's Windows machine:
```
ssh -L <dashport>:127.0.0.1:<dashport> root@102.208.217.192
# then open http://127.0.0.1:<dashport> in the Windows browser
```
Confirm the dashboard's auth gate (token) is in place before any tunnel use.

**Step 3: Decision point**

If the dashboard visual is wanted, keep this step; if `/kanban` in chat is enough, mark the dashboard optional and move on. (Recommendation: `/kanban` first; dashboard is sugar.)

---

### Task 5: End-to-end verification with the user

**Objective:** Prove the loop works for both sides.

**Step 1: Agent side**

Create three cards mirroring the next three real tasks (or three demo tasks), move one to `blocked`, comment on it, leave one in `todo`.

**Step 2: User side**

Ask the user to run `/kanban list` in the desktop chat and confirm he sees the same three cards. Optionally open the dashboard via tunnel (if Task 4 Step 2 was kept).

**Step 3: Cleanup**

Demo cards: `hermes kanban complete <id>` then `hermes kanban archive <id>` (or delete via the board DB — prefer archive; the board keeps history).

---

### Task 6 (OPTIONAL): Daily board digest

**Objective:** A morning summary of open cards delivered to the user's Telegram.

**Files:** `~/.hermes/scripts/kanban-digest.sh` (or inline in cron)

**Step 1:** Script prints a compact digest:
```bash
#!/usr/bin/env bash
out=$(hermes kanban list 2>/dev/null | grep -Ev "no matching tasks")
[ -z "$out" ] && exit 0   # silent when nothing open (watchdog pattern)
echo "Kanban board:"
echo "$out"
```
**Step 2:** Cron: `cronjob(action="create", schedule="0 8 * * *", no_agent=true, script=~/.hermes/scripts/kanban-digest.sh)` — delivers verbatim to Telegram, silent when the board is empty.

YAGNI note: skip unless the user wants the daily ping.

---

## 5. Verification (whole-system checklist)

- [ ] `hermes kanban boards list` → `default` board; `hermes kanban list` shows the demo cards.
- [ ] Full lifecycle works: create → block → comment → complete (Task 2 Step 3).
- [ ] `/kanban list` in the desktop chat shows the same cards the agent sees.
- [ ] `skill_view(kanban-task-tracking)` loads clean; a fresh session that tracks tasks updates the board without being told.
- [ ] (Optional) Dashboard Kanban tab reachable via SSH tunnel, behind its auth gate.

## 6. Risks, tradeoffs, and open questions

- **No `start`/`running` CLI verb:** `running` is dispatcher-set when a worker claims a task. The human-agent flow uses `todo → blocked → review → done` + comments instead — documented in the skill. If live "in progress" visibility is wanted later, enable the `kanban` toolset for the profile (or use a worker dispatch) — out of scope now.
- **Agent updates via CLI, not `kanban_*` tools:** correct for normal sessions (zero schema footprint by design); the tools appear automatically when a dispatcher spawns a worker. No action needed.
- **Single board assumption:** if the user later wants separate streams (e.g. REELS vs. autoclipping vs. personal), `hermes kanban boards create <slug> --switch` splits cleanly; the skill's `--board <slug>` pitfall covers it.
- **Open question:** dashboard vs. `/kanban`-only viewing (Task 4 Step 3). Default: `/kanban` in chat; dashboard via tunnel only if requested.
- **Open question:** daily digest (Task 6). Default: skip until requested.

## 7. Execution handoff

After approval: execute task-by-task with a fresh subagent per task (spec-compliance review, then code-quality review). Tasks 1–5 are each under 10 minutes; the whole plan is a single sitting. Then confirm the standing rule with the user and offer the two optional extras.
