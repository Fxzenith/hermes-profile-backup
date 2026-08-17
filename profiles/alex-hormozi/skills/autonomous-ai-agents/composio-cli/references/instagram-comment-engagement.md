# Instagram comment-engagement loop (Composio) — full recipe

Built Aug 2026 for @ze.nith001 (IG user 28532466729677348, connection `instagram_magog-daroo`).
Script: `/root/Instagram daily auto-post/scripts/comment_loop.py` (note: folder name has SPACES —
always quote paths). State: `logs/comment_state.json`.

## Goal
Run AFTER every published post: (1) post ONE self-question comment to seed discussion,
(2) reply to every unreplied top-level comment from OTHER users — once, never double-reply,
never reply to your own comments, never engage nested replies.

## Tool calls (all via `composio execute <TOOL> --account instagram_magog-daroo -d '{...}'`)

| Step | Tool | Payload |
|---|---|---|
| Find latest media | `INSTAGRAM_GET_IG_USER_MEDIA` | `{"ig_user_id": "<ID>", "fields": "id,caption,permalink,timestamp,media_type", "limit": 5}` |
| List comments | `INSTAGRAM_GET_IG_MEDIA_COMMENTS` | `{"ig_media_id": "<id>", "fields": "id,text,username,timestamp,parent_id", "limit": 50}` |
| Post self-question | `INSTAGRAM_POST_IG_MEDIA_COMMENTS` | `{"ig_media_id": "<id>", "message": "Which habit are you building this week? 👇"}` |
| Reply to comment | `INSTAGRAM_POST_IG_COMMENT_REPLIES` | `{"ig_comment_id": "<id>", "message": "..."}` (≤300 chars) |
| Check replies exist | `INSTAGRAM_GET_IG_COMMENT_REPLIES` | `{"ig_comment_id": "<id>", "fields": "id,text,username"}` |
| Remove bad reply | `INSTAGRAM_DELETE_COMMENT` | `{"ig_comment_id": "<id>"}` |

## Pitfalls (each one hit live)

1. **Comments list contains YOUR OWN comments and nested replies.** Top-level items from
   other users may have `username: null` (friend comments often do!). Nested replies carry
   `parent_id`. Own comments carry your username (`ze.nith001`). Filter order that works:
   - skip if `parent_id` present (nested)
   - skip if `username.lower()` in your own handles (`ze.nith001`, `zenith`, `ze.nith`)
   - skip if already in `replied_comments[]`
   - skip if `GET_IG_COMMENT_REPLIES` returns items (already answered)
2. **`username: null` → never format `@friend`.** Positional/user templates must be chosen
   AFTER checking username; keep two template pools (with/without `{user}`). A real reply
   containing `@friend` went live once — delete via `INSTAGRAM_DELETE_COMMENT` and re-post.
3. **Dry-run must not persist state.** The first version's dry-run appended comment IDs to
   `replied_comments[]` and saved → the next real run skipped the only fan comment. Fix:
   `if not args.dry_run: save_state(state)`.
4. **`limit` is an integer.** `"5"` (string) → `Input validation failed ... Expected integer`.
5. **Media IDs are ~17-digit strings.** Typo → `IGApiException code 100: Object with ID '...'
   does not exist`. Extracted programmatically from GET responses, never hand-typed.
6. **Verify after delete/re-post** — the wrong-ID delete returned `successful: false` with
   no error payload beyond the message; re-list comments to confirm the live thread is clean.
7. `composio execute ... -d '{"fields": "..."}'` for GET_IG_USER_MEDIA: the list is under
   `data.data` (nested), and may be large → check `storedInFile`/`outputFilePath` before
   assuming the payload is inline.

## Sweep mode (catch comments that arrive hours later)

The once-at-publish run only engages the NEWEST post at 11:02 — a comment at 18:00 is
missed until the next day, and by then "latest media" is tomorrow's post. Fix:
- `comment_loop.py --recent N` walks the last N media (newest first), replying to every
  unreplied top-level comment from other users. Self-question seeding stays restricted to
  the NEWEST post only (`allow_self = i == 0`), so old posts never collect fake prompts.
- Helper `get_recent_media_ids(limit)` replaces `get_latest_media_id()`.
- This immediately surfaced 3 backlogged "Send me this post" comments on older posts that
  the one-shot loop had never seen — swept them all in one run.

## Watchdog cron (silent 2-hourly sweep)

Pattern proven live: `no_agent` cron job running the sweep every 2h at
`0 12,14,16,18,20,22 * * *`, delivering ONLY when work happened:
- Wrapper script prints a short summary only when replies were posted (`"📬 N new comment
  reply(ies)"`); idle runs print NOTHING → cron job stays silent (non-empty stdout is what
  gets delivered).
- **Cron script paths must be relative to `~/.hermes/scripts/`** — an absolute path like
  `/root/Instagram daily auto-post/scripts/comment_sweep.py` is rejected at job creation
  ("Script path must be relative to ~/.hermes/scripts/"). Put a thin launcher there that
  execs the real script; `no_agent=true` means zero LLM cost per tick.
- State file makes it idempotent across runs; sweep + state == never double-reply, even
  when the 11:00 loop and the watchdog both target the same media.

## State shape

```json
{
  "18161765242414389": {
    "self_comment_id": "18178605952423775",
    "replied_comments": ["18117508013488535"]
  }
}
```

## Cron wiring
The daily job prompt (cron jobs.json) has a `STEP 3b — COMMENT ENGAGEMENT LOOP` step:
run `python3 scripts/comment_loop.py` after every successful publish. The job's workdir was
renamed from `/root/instagram-thread-carousel` to the spaced path; both the `workdir` field
and the "Work from …" line in the prompt had to be updated in `/root/.hermes/cron/jobs.json`.

## Reuse
Copy `scripts/comment_loop.py` as the starting point for any IG-API-only engagement loop.
Adjust: account, IG_USER_ID, own-username set, reply/self-question template pools.