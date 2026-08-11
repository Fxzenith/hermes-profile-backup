# Instagram auto-poster pipeline — operational facts

Session record: 2026-08-09 (diagnostic + directory rename). Cron job id `18d280b4af39`.

## Identity

- Job name: "Instagram daily auto-post (self-healing)"
- Schedule: `0 11 * * *` (11:00 SAST, server TZ is SAST +02:00)
- Deliver: `telegram:-1003938786142` (CONFERENCE ROOM home channel)
- Config source of truth: `/root/.hermes/cron/jobs.json`
- Run output history: `/root/.hermes/cron/output/18d280b4af39/<timestamp>.md`
- **Workdir: `/root/Instagram daily auto-post`** (renamed 2026-08-09 from `/root/instagram-thread-carousel`; path HAS SPACES — always quote in shell)

## Accounts / connections (Composio)

- Primary: `instagram_magog-daroo` — **ACTIVE**, real account @ze.nith001, IG user id `28532466729677348` (MEDIA_CREATOR)
- Alternates: `instagram_forky-eyne`, `instagram_diota-canary` — EXPIRED but **unused**; do not chase them while primary is ACTIVE
- Post flow: `INSTAGRAM_POST_IG_USER_MEDIA` (pass local PNG as `image_file` in `-d`) → `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` (keep `max_wait_seconds` > 0)
- Verify independently: `~/.composio/composio execute INSTAGRAM_GET_IG_USER_MEDIA --account instagram_magog-daroo -d '{"ig_user_id":"28532466729677348"}'`

## Scripts (in workdir)

- `scripts/self_heal.py` — pre-flight health check. Exit contract: 0 = healthy; 2 = connection present but primary not ACTIVE (swap `ACCOUNT` in composio_post.py if an alternate is ACTIVE); 3 = composio CLI missing/broken. Has hardcoded `WORKDIR = Path(...)` constant.
- `scripts/composio_post.py` — generate image + post; built-in retry/backoff for transient errors (rate limits, 9007 publish-too-soon, code 9); refuses to retry permanent auth errors. Hardcodes `ACCOUNT` + `IG_USER_ID`.
- `logs/cron.log` — pipeline log (generation + publish attempts).
- `workspace/YYYY-MM-DD/post-NN/` — per-post config.json / post.png / post_meta.json.

## Session learnings (2026-08-09)

1. **"Didn't trigger" was a false alarm**: user reported last post "1d ago". Cron `last_run_at` was 2026-08-08 11:02 status `ok`; server clock was 08:49 on the 9th; `next_run_at` 11:00 same day. The 1-day-old post WAS yesterday's successful run; today's run simply hadn't fired yet. Nothing was broken.
2. **Engagement ≠ trigger**: the post had 1 like — that's a reach problem, not a firing problem. Suggested replying to the "Send me This Post 🙏" comment rather than touching pipeline code.
3. **Rename executed**: user said "change the name" pointing at the workdir; the job `name` field already said "Instagram daily auto-post (self-healing)" — they meant the FOLDER. Renamed dir, patched `self_heal.py` WORKDIR, docstring `cd` examples in composio_post.py/cron_post.py, and jobs.json `workdir` + `Work from ...` prompt token. Re-ran `self_heal.py` from new path → exit 0 healthy. Memory updated with "path has spaces — quote it" note.
