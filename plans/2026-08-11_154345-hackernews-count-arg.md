# Hackernews Skill: Configurable Count (`/hackernews N`) Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the `/hackernews` skill return the top N stories — default 15 when no number is given, exactly N when the user types `/hackernews N`.

**Architecture:** The skill already separates concerns cleanly: the agent reads `/hackernews [N]`, parses N, and shells out to `top15.py`. The only changes needed: (1) `top15.py` accepts an optional positional count argument, (2) `SKILL.md` documents the new invocation contract for the agent. No new dependencies, no API changes.

**Tech Stack:** Python 3 stdlib only (`sys.argv`, `argparse`-free), existing Composio CLI shell-out unchanged.

---

## Current Context

- Script: `/root/.hermes/skills/social-media/hackernews/scripts/top15.py` — hardcodes `TOP_N = 15` (line 15), slices `ids = ids[:TOP_N]` (line 47), writes cache to fixed `last_top15.json` (line 71).
- Skill doc: `/root/.hermes/skills/social-media/hackernews/SKILL.md` — Step 1 invokes `python3 .../top15.py` with no args; Pitfalls section warns about "15 sequential CLI calls".
- The slash command is parsed by the agent, so the **agent** must forward the user's number as `argv[1]`.

## Proposed Behavior Contract

| User input | Script call | Output |
|---|---|---|
| `/hackernews` | `top15.py` | top 15 (unchanged default) |
| `/hackernews 1` | `top15.py 1` | top 1 |
| `/hackernews 5` | `top15.py 5` | top 5 |
| `/hackernews abc` | `top15.py abc` | error message, exit 1 (invalid) |
| `/hackernews 999` | `top15.py 999` | clamp to 500 (max HN returns), plus stderr note |

---

## Task 1: Parse optional count in `top15.py`

**Objective:** Script reads N from `sys.argv[1]`; defaults to 15; validates range 1–500.

**Files:**
- Modify: `/root/.hermes/skills/social-media/hackernews/scripts/top15.py:15` (replace `TOP_N = 15`)

**Step 1: Replace the constant with a runtime value**

Replace line 15:

```python
TOP_N = 15
```

with:

```python
# Removed: TOP_N hardcode — count now comes from CLI arg (default 15).
```

**Step 2: Add arg parsing at the top of `main()`**

In `main()`, immediately after the `not os.path.exists(COMPOSIO)` guard (after line 40), insert:

```python
    top_n = 15
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        if not raw.isdigit():
            print(f"ERROR: invalid count '{raw}' — pass a number 1-500 (e.g. /hackernews 5)", file=sys.stderr)
            return 1
        top_n = int(raw)
        if top_n < 1:
            print("ERROR: count must be at least 1", file=sys.stderr)
            return 1
        if top_n > 500:
            print(f"note: HN returns at most 500 stories; clamping {top_n} -> 500", file=sys.stderr)
            top_n = 500
```

**Step 3: Use `top_n` for the slice**

Replace line 47 (`ids = ids[:TOP_N]`) with:

```python
    ids = ids[:top_n]
```

**Step 4: Make the cache filename reflect the count**

Replace line 71 (`last_top15.json`) with:

```python
    with open(os.path.expanduser(f"~/.hermes/skills/social-media/hackernews/scripts/last_top{top_n}.json"), "w") as fh:
```

**Step 5: Update module docstring (optional but cheap)**

Line 2: `"""Fetch the top 15 trending stories` → `"""Fetch the top N trending stories (default 15; pass a number to override).`

**Step 6: Commit**

```bash
git -C /root/hermes-profile-backup add . 2>/dev/null; cd /root/.hermes/skills/social-media/hackernews && git init -q 2>/dev/null
# (skills dir may not be a git repo — if so, skip git; just note files changed)
```

Note: `~/.hermes` is backed up via the daily profile-backup cron — no manual git needed. Skip commit if the skills tree isn't a repo.

## Task 2: Update `SKILL.md` invocation contract

**Objective:** Agent knows to pass the user's number through and adjust output format expectations.

**Files:**
- Modify: `/root/.hermes/skills/social-media/hackernews/SKILL.md`

**Step 1: Rewrite Step 1 of the Skills section**

Replace:

```markdown
1. **Run the fetch script** (does everything: top stories + per-story details):
   ```bash
   python3 ~/.hermes/skills/social-media/hackernews/scripts/top15.py
   ```
```

with:

```markdown
1. **Parse the count** — if the user typed `/hackernews N`, capture N. Default is 15.
2. **Run the fetch script** (does everything: top stories + per-story details; optional count arg):
   ```bash
   python3 ~/.hermes/skills/social-media/hackernews/scripts/top15.py        # top 15 (default)
   python3 ~/.hermes/skills/social-media/hackernews/scripts/top15.py 1      # top 1
   python3 ~/.hermes/skills/social-media/hackernews/scripts/top15.py 5      # top 5
   ```
   Pass the user's number as the argument — the script handles validation and clamping to 500.
```

**Step 2: Update "When to Use" trigger list**

Add slash-command patterns: `/hackernews 1`, `/hackernews 3`, "top 5 HN stories", "HN top N" with N as a variable.

**Step 3: Adjust Pitfalls bullets**

- Change "15 sequential CLI calls take ~1.5-2 min" → "N sequential CLI calls take ~0.1 min each (15 ≈ 2 min); smaller N is proportionally faster — do NOT run item fetches inline one-by-one in the agent loop; always use the script."
- Add a bullet: "Script exit code tells the story — non-zero = invalid count; relay the stderr message verbatim."

**Step 4: Adjust Verification section**

Replace "Script prints exactly 15 numbered entries" with "Script prints exactly N numbered entries (15 when no arg given); invalid args error out with exit 1."

## Task 3: Verify end-to-end

**Objective:** Prove all three invocation shapes behave correctly.

**Step 1: Run the old default**

Run: `python3 /root/.hermes/skills/social-media/hackernews/scripts/top15.py`
Expected: 15 numbered entries (may take ~2 min).

**Step 2: Run with small count**

Run: `python3 /root/.hermes/skills/social-media/hackernews/scripts/top15.py 3`
Expected: exactly 3 entries, same front-page IDs as the first 3 of the full run (rank order preserved), and a `last_top3.json` cache file appears.

**Step 3: Run with invalid input**

Run: `python3 /root/.hermes/skills/social-media/hackernews/scripts/top15.py abc; echo $?`
Expected: ERROR message on stderr, exit code 1, no partial output.

**Step 4: Sanity cross-check (order preserved)**

Verify entry 1 of `top15.py 1` matches entry 1 of `top15.py 15` — the ID order from `GET_TOP_STORIES` is the front-page rank and must not be re-sorted.

---

## Files Likely to Change

- `/root/.hermes/skills/social-media/hackernews/scripts/top15.py`
- `/root/.hermes/skills/social-media/hackernews/SKILL.md`
- (generated per-run, not committed) `~/.hermes/skills/social-media/hackernews/scripts/last_top<N>.json`

## Risks & Tradeoffs

- **Count > actual stories returned:** HN API can return fewer than requested near the tail; script silently prints what exists. Acceptable — slice handles it.
- **Cache filename churn:** `last_top3.json`, `last_top15.json`, etc. accumulate. Acceptable (tiny files, inbox-like hygiene); optionally consolidate into one `last_trending.json` if it bothers anyone.
- **Agent-parsing slip:** if the agent forgets to forward N, user gets 15. Mitigated by the rewritten Step 1 in SKILL.md — the agent must parse the count in the same breath as detecting the slash command.
- **No re-sort guarantee** remains the top correctness invariant — slice-of-ranked-IDs only, never sort by points.

## Open Questions

- Should `/hackernews 0` error or mean "just the header/theme"? Plan says error; open to flip.
- Keep `last_top15.json` naming for backward compat with any downstream consumer? (Currently no known consumer besides the script itself.)